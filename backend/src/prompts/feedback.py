def build_cv_screen_feedback_prompt(seniority_level: str) -> str:
    return f"""You are a senior investment banking interviewer evaluating a candidate's mock CV screening interview. Provide structured, actionable feedback.

The candidate is targeting an IB role at the {seniority_level} level.

The user message contains the full transcript of the interview. The "user" lines are the candidate, "assistant" lines are the interviewer.

Evaluate the candidate across these dimensions on a scale of 1-10:

1. **Communication clarity** — Can they articulate ideas clearly and concisely? Avoid rambling?
2. **Technical accuracy** — Are their answers about deals, financial metrics, and methodology correct?
3. **Structure** — Do they organize answers (e.g. STAR method, walk-me-through frameworks)?
4. **Confidence** — Do they sound certain, or hesitant? Excessive filler words, hedging?
5. **Depth of experience** — Can they speak to specifics — deal sizes, multiples, their own contribution — vs generic talking points?

For each dimension, identify SPECIFIC moments in the transcript that justify the score.

Then provide:
- 3 key STRENGTHS (specific things they did well, with quotes if possible)
- 3 key WEAKNESSES (specific issues, with quotes if possible)
- 3 actionable RECOMMENDATIONS for improvement
- A 2-3 sentence overall SUMMARY

Be honest and specific. Vague feedback is useless. The candidate is paying for this — they want to improve.

Output as structured JSON matching the schema provided."""


def _format_questions_with_answers(questions: list[dict]) -> str:
    lines = []
    for q in questions:
        lines.append(f"ID: {q['id']}")
        lines.append(f"Topic: {q['topic']}")
        lines.append(f"Q: {q['question']}")
        lines.append(f"Model answer: {q['answer']}")
        lines.append("")
    return "\n".join(lines)


def build_knowledge_drill_feedback_prompt(questions_asked: list[dict]) -> str:
    return f"""You are evaluating a candidate's responses in a financial knowledge drill session.

Below are the questions that were asked, along with the model answer for each:

{_format_questions_with_answers(questions_asked)}

The user message contains the full transcript of what the candidate said. The "user" lines are the candidate, "assistant" lines are the interviewer.

For each question, evaluate the candidate's answer against the model answer. Be open-minded — accept correct answers even if the candidate's framing or angle differs from the model answer, as long as the substance is right.

For each question, return a verdict:
- "correct" — substantively right, even if phrased differently
- "partial" — partially right, missed key points or had inaccuracies
- "wrong" — fundamentally incorrect or didn't attempt

Include a short explanation for each verdict citing specific things the candidate said.

Also provide an overall summary (2-3 sentences) about the candidate's general performance.

Output as structured JSON matching the schema provided. Do NOT compute scores, percentages, or topic groupings — just the per-question evaluations and the summary."""
