"""Pure helpers, prompts, and thresholds for the live-interview flow.

Extracted verbatim out of app/services/ai_screening_service.py (which had
grown into one 1700+ line "God service" covering session CRUD, question
generation, evaluation, and the live-interview conversation loop). These
functions have no dependency on AIScreeningService instance state — they
only take plain arguments — so moving them here is a pure code-location
change with no behavior change.
"""

from __future__ import annotations

from app.models.candidate import Candidate


def _infer_seniority(candidate: Candidate | None) -> str:
    if not candidate:
        return "mid-level"
    years = getattr(candidate, "years_experience", None)
    if years is None:
        # Try parsed resume data
        parsed = getattr(candidate, "parsed_resume_data", None) or {}
        years = parsed.get("years_of_experience")
    if years is None:
        return "mid-level"
    try:
        years = float(years)
    except (TypeError, ValueError):
        return "mid-level"
    if years < 2:
        return "junior"
    elif years < 5:
        return "mid-level"
    elif years < 9:
        return "senior"
    else:
        return "lead/principal"

# ── Live interview prompts ────────────────────────────────────────────────────

_OPENING_QUESTION = (
    "Can you briefly introduce yourself and walk me through your professional background?"
)

# ── Mandatory recruiter logistics questions ───────────────────────────────────
# These are ALWAYS asked after the AI assessment questions, regardless of
# max_questions.  They are excluded from AI scoring — only assessed questions
# contribute to scores and recommendations.

_LOGISTICS_QUESTIONS: list[str] = [
    "Thank you — just a couple of quick practical questions for the hiring team. "
    "What is your current notice period, and when would you be available to start if you were offered this role?",

    "What are your current and expected compensation expectations? "
    "Please mention your current package and what you're looking for in your next role.",

    "Finally, do you have any questions for us about the role, the team, or the company? "
    "Feel free to ask anything that would help you decide.",
]

_N_LOGISTICS = len(_LOGISTICS_QUESTIONS)   # 3

# ── Candidate Q&A phase ───────────────────────────────────────────────────────
# After the final logistics question ("Do you have any questions?") the AI must
# genuinely RESPOND to whatever the candidate asks — not end the interview.
# Up to _CANDIDATE_QA_MAX_ROUNDS exchanges are allowed before the AI closes.

_CANDIDATE_QA_MAX_ROUNDS = 2   # max candidate question→AI answer rounds

_CANDIDATE_QA_SYSTEM_PROMPT = """\
You are the AI interviewer for {company} conducting a candidate Q&A.
The candidate just asked you a question about the role or company.

Context you have available:
{job_context}

Rules:
- Answer the candidate's question concisely and honestly using the context above.
- If you do not have specific information, say so warmly and suggest they ask the recruiter.
- Keep the response to 2–4 sentences maximum.
- After answering, invite follow-up: "Is there anything else you'd like to know?"
- Do NOT ask assessment questions — you are in the closing Q&A phase.
- Return ONLY your response — no preamble, labels, or system notes.
"""

_CANDIDATE_QA_CLOSING = (
    "Thank you so much for your time today — it was great speaking with you. "
    "The recruitment team will review your responses and be in touch soon. "
    "We wish you all the best!"
)

_LIVE_SYSTEM_PROMPT = """\
You are a senior recruitment specialist conducting an initial candidate screening interview.

Rules:
- Ask ONE question at a time — never multiple questions in a single message.
- Build follow-up questions from what the candidate actually says.
- Topics to cover: work experience, key projects, career goals, salary expectations, \
notice period, team fit, motivation, and role understanding.
- NEVER ask technical coding questions, algorithms, or whiteboard problems.
- Keep the tone warm, conversational, and professional.
- Return ONLY the question — no preamble, labels, or lists.
- One or two sentences maximum per question.

Routing rules:
- Candidate mentions a project → ask about their specific contribution and impact.
- Candidate mentions leadership → ask about team size and management approach.
- Candidate mentions career change → ask about motivation for the switch.
- Candidate mentions redundancy / layoff → ask sensitively about current situation.
- After 12+ questions → ask about notice period or salary if not yet covered.
"""

# ── Scoring thresholds ────────────────────────────────────────────────────────
# These are enforced in Python BEFORE calling Groq. The LLM never sees
# insufficient data — it cannot hallucinate scores for a partial transcript.

_MIN_CANDIDATE_WORDS       = 200   # total words across all candidate messages — hard gate
_MIN_ANSWER_COVERAGE       = 0.80  # candidate must answer ≥ 80% of questions asked — hard gate
_RECOMMENDED_DURATION_SECS = 300   # 5 min — below this a low-confidence warning is added but
                                   # scoring is NOT blocked; duration alone never fails an interview
_MIN_TURN_WORDS            = 3     # minimum words to treat one turn as a real answer
_MIN_TURN_CHARS            = 12    # avoid progressing on filler like "yes" / "ok"

_ASSESSMENT_SYSTEM_PROMPT = """\
You are an expert HR analytics engine evaluating a completed screening interview.

STRICT RULES — READ BEFORE SCORING:
1. Only score dimensions for which the transcript contains DIRECT EVIDENCE.
   If the transcript lacks evidence for a dimension, score it 40 (insufficient data).
2. Every strength and concern MUST include a direct quote or specific paraphrase
   from the transcript as evidence. No generic statements allowed.
3. DO NOT invent, assume, or extrapolate information not present in the transcript.
4. If the candidate gave vague or one-word answers, score them low (30–45).
5. Scores must reflect actual transcript content, not job-title assumptions.

OUTPUT FORMAT (return ONLY valid JSON, no prose, no markdown):
{
  "communication_score": <0-100 integer, based on clarity, fluency, structure>,
  "experience_score": <0-100 integer, based on concrete examples given>,
  "confidence_score": <0-100 integer, based on decisiveness and specificity>,
  "culture_fit_score": <0-100 integer, based on collaboration/values signals>,
  "leadership_score": <0-100 integer, based on evidence of leadership, team management, or initiative; score 40 if no evidence>,
  "overall_score": <0-100 integer, weighted composite>,
  "recommendation": "<strong_hire|hire|consider|reject>",
  "strengths": [
    {"claim": "<one-line strength>", "evidence": "<direct quote or paraphrase>"}
  ],
  "concerns": [
    {"claim": "<one-line concern>", "evidence": "<direct quote or paraphrase>"}
  ],
  "salary_expectation": "<exact text from transcript or null>",
  "notice_period": "<exact text from transcript or null>",
  "career_goals": "<verbatim or close paraphrase from transcript, or null>",
  "key_projects_mentioned": ["<only projects explicitly named by candidate>"],
  "ai_summary": "<3-4 sentence factual summary based strictly on transcript>"
}

SCORING THRESHOLDS:
  strong_hire: 85+  (clear strengths, strong evidence across multiple areas)
  hire:        70–84 (solid performance, good evidence)
  consider:    55–69 (mixed performance, some gaps)
  reject:      <55   (significant concerns, vague/weak answers)

EVIDENCE REQUIREMENT:
  - A strength with no direct transcript evidence MUST NOT be listed.
  - A concern with no direct transcript evidence MUST NOT be listed.
  - Generic phrases like "good communicator" without evidence → omit entirely.
"""


def _auto_end_heuristic(last_answer: str, q_count: int) -> bool:
    """Return True if the interview should wrap up automatically."""
    if q_count < 8:
        return False
    goodbyes = {"thank you", "thanks for having me", "goodbye", "that's all", "no more questions"}
    return any(phrase in last_answer.lower() for phrase in goodbyes)


def _fallback_question(q_num: int) -> str:
    """Generic follow-up when Groq is unavailable."""
    bank = [
        "Can you tell me about a project you are particularly proud of?",
        "What motivates you most in your day-to-day work?",
        "How do you handle sudden changes in priorities?",
        "Tell me about a time you worked closely with a difficult colleague.",
        "What are your career goals for the next two to three years?",
        "What is your current notice period, and what are your salary expectations?",
        "Why are you interested in this particular role?",
        "What questions do you have for us about the team or company?",
    ]
    return bank[min(q_num - 1, len(bank) - 1)]


def _is_no_questions(text: str) -> bool:
    """Return True when the candidate indicates they have no questions."""
    lowered = (text or "").lower().strip()
    no_patterns = [
        "no ", "nope", "not really", "nothing", "none",
        "i'm good", "i am good", "that's all", "that is all",
        "no questions", "no thank", "thank you, no",
    ]
    return any(lowered.startswith(p) or p in lowered[:80] for p in no_patterns)


def _answer_candidate_question(screening: "AIScreening", question: str, db: "Session") -> str:
    """Use Groq to answer the candidate's question using job description context."""
    from app.services.groq_interview_client import GroqInterviewClient, GroqInterviewUnavailableError
    from app.models.job import Job

    job_title = screening.job_title_snapshot or "Unknown Role"
    job_description = ""
    if screening.job_id:
        try:
            job = db.get(Job, screening.job_id)
            if job:
                job_description = (job.description or "")[:2000]
        except Exception:
            pass

    job_context = f"Role: {job_title}\n\nJob Description:\n{job_description}" if job_description \
        else f"Role: {job_title}"

    system_prompt = _CANDIDATE_QA_SYSTEM_PROMPT.format(
        company="the company",
        job_context=job_context,
    )

    groq = GroqInterviewClient()
    try:
        resp = groq.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.5,
            max_tokens=300,
        )
        return resp.content.strip()
    except GroqInterviewUnavailableError:
        return (
            "That's a great question — the recruiting team will be able to provide "
            "you with full details when they follow up. Is there anything else you'd like to know?"
        )


def is_substantive_answer(text: str) -> bool:
    """Return True when the candidate answer has enough content to progress."""
    cleaned = (text or "").strip()
    if len(cleaned) < _MIN_TURN_CHARS:
        return False
    words = [w for w in cleaned.split() if w.strip()]
    return len(words) >= _MIN_TURN_WORDS
