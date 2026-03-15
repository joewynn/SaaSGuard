"""PromptBuilder – assembles structured prompts from SummaryContext.

Every prompt contains a [CONTEXT] block with ONLY the facts from DuckDB.
The system prompt explicitly constrains the LLM to reference only those facts.
This is the primary hallucination-prevention mechanism at the prompt level.
"""

from __future__ import annotations

from src.domain.ai_summary.entities import SummaryContext


class PromptBuilder:
    """Builds grounded prompts for the LLM from structured SummaryContext data.

    Business Context: Prompt structure is the first line of defence against
    hallucination. By providing a [CONTEXT] block with only verified facts and
    a [CONSTRAINT] that explicitly forbids extrapolation, we reduce the LLM's
    tendency to invent figures or feature names.
    """

    def build_summary_prompt(self, context: SummaryContext, audience: str) -> str:
        """Assemble a summary generation prompt for the given audience.

        Business Context: CSM prompts focus on actionable tactics; executive
        prompts focus on revenue impact and ROI of intervention. Both include
        the same [CONTEXT] block so the same facts ground both narratives.

        Args:
            context: All verified facts from DuckDB for this customer.
            audience: 'csm' for Customer Success Manager, 'executive' for VP/C-suite.

        Returns:
            Complete prompt string ready to send to the LLM.
        """
        ctx_block = self._format_context(context)

        if audience == "csm":
            instruction = (
                "Write a 3-5 sentence briefing for a Customer Success Manager. "
                "Lead with the top churn driver from the SHAP features. "
                "Include 2 specific recommended actions based on the data. "
                "Mention any open high-priority support tickets if present. "
                "Tone: practical, direct, urgent if risk tier is HIGH or CRITICAL."
            )
        else:  # executive
            instruction = (
                "Write a 3-sentence executive summary for a VP of Customer Success. "
                "Lead with annual revenue at risk (MRR × 12). "
                "State the single most important risk factor from the SHAP features. "
                "Close with the estimated ROI of CS intervention (assume 10-15% churn reduction). "
                "Tone: concise, quantified, boardroom-ready."
            )

        return (
            f"[CONTEXT]\n{ctx_block}\n\n"
            f"[INSTRUCTION]\n{instruction}\n\n"
            f"[CONSTRAINT]\n"
            f"You may ONLY reference facts listed in [CONTEXT]. "
            f"Do not infer, extrapolate, or add any information not explicitly stated above. "
            f"Do not use phrases like 'I think', 'probably', or 'might be'."
        )

    def build_question_prompt(self, context: SummaryContext, question: str) -> str:
        """Assemble a Q&A prompt that constrains answers to available customer data.

        Business Context: The RAG chatbot answers free-text questions from CSMs
        about a specific customer. The [CONSTRAINT] block prevents the LLM from
        fabricating information not present in the customer's DuckDB history.

        Args:
            context: All verified facts from DuckDB for this customer.
            question: The CSM's free-text question (5–500 characters).

        Returns:
            Complete prompt string ready to send to the LLM.
        """
        ctx_block = self._format_context(context)
        return (
            f"[CONTEXT]\n{ctx_block}\n\n"
            f"[QUESTION]\n{question}\n\n"
            f"[CONSTRAINT]\n"
            f"Answer using ONLY facts in [CONTEXT]. "
            f"If the question cannot be answered from the context, reply exactly: "
            f"'I cannot answer this from the available customer data.'"
        )

    def _format_context(self, context: SummaryContext) -> str:
        """Format a SummaryContext into a structured text block for the prompt.

        Args:
            context: The SummaryContext to format.

        Returns:
            Multi-line string with labelled sections for each data source.
        """
        c = context.customer
        p = context.prediction

        shap_lines = "\n".join(
            f"  - {f.feature_name}: value={f.feature_value:.4g}, shap_impact={f.shap_impact:+.4g}"
            for f in p.top_shap_features[:5]
        )

        ticket_lines = (
            "\n".join(
                f"  - priority={t.get('priority')}, topic={t.get('topic')}, "
                f"age_days={t.get('age_days')}"
                for t in context.open_tickets
            )
            if context.open_tickets
            else "  (none)"
        )

        event_lines = (
            "\n".join(
                f"  - {etype}: {count}"
                for etype, count in context.events_last_30d_by_type.items()
            )
            if context.events_last_30d_by_type
            else "  (none)"
        )

        gtm_block = (
            f"  stage={context.gtm_opportunity.get('stage')}, "
            f"amount={context.gtm_opportunity.get('amount')}"
            if context.gtm_opportunity
            else "  (none)"
        )

        return (
            f"Customer Profile:\n"
            f"  customer_id: {c.customer_id}\n"
            f"  industry: {c.industry}\n"
            f"  plan_tier: {c.plan_tier}\n"
            f"  mrr: ${c.mrr.amount:,.2f}/mo  (ARR: ${c.mrr.amount * 12:,.2f})\n"
            f"  tenure_days: {c.tenure_days}\n"
            f"  is_early_stage: {c.is_early_stage}\n"
            f"\n"
            f"Churn Prediction:\n"
            f"  churn_probability: {p.churn_probability.value:.1%}\n"
            f"  risk_tier: {p.churn_probability.risk_tier}\n"
            f"  risk_score: {p.risk_score.value:.1%}\n"
            f"  recommended_action: {p.recommended_action}\n"
            f"\n"
            f"Top SHAP Feature Drivers (positive shap_impact = increases churn risk):\n"
            f"{shap_lines}\n"
            f"\n"
            f"Usage Events (last 30 days by type):\n"
            f"{event_lines}\n"
            f"\n"
            f"Open Support Tickets:\n"
            f"{ticket_lines}\n"
            f"\n"
            f"GTM Opportunity:\n"
            f"{gtm_block}\n"
            f"\n"
            f"Cohort Context:\n"
            f"  cohort_churn_rate (same tier + industry): {context.cohort_churn_rate:.1%}"
        )
