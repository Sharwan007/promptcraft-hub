"""Transparent, deterministic, rule-based prompt quality scoring and diagnosis.

This is NOT artificial intelligence. Each component gets a strength between 0 and 1 from
several independent signals (labelled sections, phrase patterns, length, counts of distinct
cues, ambiguity), which is converted to points. Penalties apply for ambiguity, conflicting
instructions and extremely short prompts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.use_case_profiles import detect_use_case, get_profile

# --------------------------------------------------------------------------- weights
WEIGHTS: list[tuple[str, str, int]] = [
    ("task", "Clear task", 20),
    ("context", "Relevant context", 15),
    ("role", "Defined role", 10),
    ("input", "Input information", 10),
    ("output_format", "Output format", 15),
    ("constraints", "Constraints", 10),
    ("audience", "Target audience", 5),
    ("quality_criteria", "Quality criteria", 10),
    ("specificity", "Reasonable specificity", 5),
]
LABELS = {k: l for k, l, _ in WEIGHTS}
LABELS["tone"] = "Tone"
DIAGNOSTIC_ORDER = ["role", "context", "task", "input", "output_format", "constraints",
                    "audience", "tone", "quality_criteria", "specificity"]

READINESS = [(90, "Excellent"), (80, "Strong"), (60, "Good"), (40, "Basic"), (0, "Needs Improvement")]


def readiness_label(score: int) -> str:
    for threshold, label in READINESS:
        if score >= threshold:
            return label
    return "Needs Improvement"


# --------------------------------------------------------------------------- lexicons
ACTION_VERBS = set("""write create draft generate summarize summarise analyze analyse compare plan brainstorm extract
transform convert rewrite translate explain list identify review evaluate build design develop prepare produce outline
suggest recommend classify categorize categorise calculate debug fix refactor optimize optimise check audit assess propose
compile document describe define map prioritize prioritise rank answer edit improve proofread simplify format give make
provide find show tell help turn act perform complete update respond reply interpret predict forecast validate test
investigate diagnose estimate determine select choose organize organise combine merge clean sort filter group""".split())
QUESTION_STARTS = ("what", "how", "why", "which", "who", "when", "where", "can", "could", "should", "is", "are", "does", "do")
STOPWORDS = set("""a an the and or of to in on for with about is are be it this that these those my our your their i me we you
please can could would should will just very really some any""".split())
DELIVERABLES = """email e-mail presentation slides slide deck report summary plan outline table query script function code list
proposal brief charter minutes letter memo article post essay document analysis checklist template spreadsheet formula
dashboard roadmap strategy stories criteria policy agenda review response reply message description paragraph
paragraphs sentence sentences itinerary schedule survey questionnaire pitch speech scenario test cases""".split()
VAGUE = ["something", "stuff", "things", "thing", "good", "nice", "better", "best", "great", "anything", "whatever", "etc",
         "maybe", "kind of", "sort of", "a bit", "a lot", "appropriate", "suitable", "as needed", "interesting",
         "somehow", "some", "various", "whenever", "decent", "proper"]
TONE_WORDS = """professional polite formal informal friendly casual persuasive empathetic empathic neutral assertive positive
warm authoritative confident courteous respectful objective factual encouraging diplomatic enthusiastic calm direct
concise plain simple humorous serious action-oriented optimistic reassuring neutral-toned""".split()
AUDIENCE_NOUNS = """executives executive stakeholders stakeholder beginners beginner customers customer clients client students
student managers manager team teams developers developer engineers engineer leadership board non-technical readers reader
users user sponsor sponsors ceo cfo cto vp directors director colleagues colleague novices professionals analysts analyst
teenagers children parents patients investors employees staff audience public committee council""".split()
ROLE_NOUNS = """expert analyst manager specialist consultant engineer developer writer editor coach advisor reviewer architect
scientist tutor teacher assistant facilitator lead officer strategist designer researcher copywriter coordinator
administrator accountant lawyer recruiter planner scrum master owner tester auditor director mentor""".split()

SECTION_LABELS = {
    "role": ["role", "persona", "act as"],
    "context": ["context", "background", "situation", "scenario"],
    "task": ["task", "objective", "goal", "instructions", "instruction", "request"],
    "input": ["input", "inputs", "data", "source", "source material", "source data", "information", "notes"],
    "output_format": ["output format", "output", "format", "deliverable", "response format"],
    "constraints": ["constraints", "constraint", "requirements", "rules", "limits", "restrictions"],
    "audience": ["audience", "target audience", "reader", "readers"],
    "tone": ["tone", "style", "voice"],
    "quality_criteria": ["quality criteria", "quality", "success criteria", "acceptance criteria", "criteria", "quality checks"],
}
_LABEL_TO_KEY = {lab: key for key, labs in SECTION_LABELS.items() for lab in labs}
_SECTION_RE = re.compile(
    r"^[ \t]*(?:#{1,4}[ \t]*)?(?:\*\*)?(" + "|".join(sorted((re.escape(l) for l in _LABEL_TO_KEY), key=len, reverse=True))
    + r")(?:\*\*)?[ \t]*[:\-–][ \t]*(?:\*\*)?(.*)$", re.IGNORECASE)

CONSTRAINT_CUES = [
    r"\b(under|below|within|no more than|at most|maximum|max\.?|up to|fewer than|less than|limit(?:ed)? to)\s+\d+",
    r"\bat least\s+\d+", r"\b\d+\s*(?:-|to)?\s*\d*\s*(words?|sentences?|bullets?|bullet points|paragraphs?|slides?|pages?|items?|options?|steps?|rows?|lines?|characters?|minutes?)\b",
    r"\b(do not|don't|never|avoid|without|exclude|excluding|must not|should not)\b",
    r"\b(must|only|always|strictly|exactly)\b", r"\b(limit|maximum|minimum|restrict)\w*\b",
    r"\b(deadline|by (?:monday|tuesday|wednesday|thursday|friday|end of)|due date)\b",
    r"\b(in (?:english|spanish|french|german|hindi)|language:)\b", r"\b(reading level|grade level|plain language|jargon)\b",
    r"\b(cite|citations?|sources?|references?)\b", r"\b(use only|based only on|only use)\b",
]
FORMAT_STRUCT_CUES = [
    r"\btables?\b", r"\bbullet(?:ed|s)?(?: points?| list)?\b", r"\bnumbered\b", r"\bjson\b", r"\bmarkdown\b", r"\bcsv\b",
    r"\boutline\b", r"\bheadings?\b", r"\bsections?\b", r"\bsubject line\b", r"\bparagraphs?\b", r"\bcode block\b",
    r"\bstep[- ]by[- ]step\b", r"\bcolumns?\b", r"\bslide[- ]by[- ]slide\b", r"\bformat(?:ted)?\b", r"\bin the form of\b",
    r"\bstructured as\b", r"\b(?:xml|yaml|html)\b", r"\bgiven[- ]when[- ]then\b", r"\bchecklist\b", r"\bone[- ]sentence\b",
    r"\bexecutive summary\b", r"\bsql query\b", r"\bheadline\b", r"\bsteps?\b",
]
QUALITY_CUES = [
    r"\b(ensure|make sure|be sure)\b", r"\b(must|should) be (?:clear|accurate|concise|actionable|specific|consistent|complete|correct|traceable|testable|measurable)",
    r"\bcriteria\b", r"\b(verify|validate|double[- ]check|check that|cross[- ]check)\b",
    r"\b(accura(?:te|cy)|actionable|testable|measurable|traceable)\b", r"\b(flag|call out|highlight)\b.*\b(assumption|gap|risk|unclear|missing|uncertain)",
    r"\b(do not|don't) (?:invent|make up|guess|fabricate|assume)\b", r"\b(if (?:you are|you're) unsure|if information is missing|if unclear)\b",
    r"\b(explain (?:why|your)|justify|rationale|reasoning|assumptions?)\b", r"\b(success|good looks like|high[- ]quality|without errors|error-free)\b",
    r"\b(cite|cites|citations?|sources?)\b",
]
CONTEXT_CUES = {
    "who": r"\b(i am|i'm|we are|we're|my (?:team|company|manager|role|project|department)|our (?:team|company|project|department|customers?|clients?|product))\b",
    "why": r"\b(because|so that|in order to|goal|objective|purpose|the aim|aim is|reason|to help|to support|to prepare|to decide)\b",
    "background": r"\b(background|context|scenario|situation|currently|recently|given that|as part of|working on|preparing for|ahead of|following)\b",
}
DOMAIN_NOUNS = r"\b(project|team|customer|client|stakeholder|company|product|department|sprint|budget|system|process|campaign|quarter|release|vendor|supplier|order|invoice|incident|ticket|launch|policy)\b"

CONFLICT_PAIRS = [
    (r"\b(brief|briefly|short|concise|one[- ]sentence|one[- ]line|tl;?dr|succinct)\b",
     r"\b(detailed|in[- ]depth|comprehensive|exhaustive|thorough|extensive|long[- ]form)\b",
     "The prompt asks for both a brief answer and a detailed/comprehensive one."),
    (r"\b(formal|professional)\b", r"\b(casual|slang|informal)\b", "The prompt asks for both a formal and a casual tone."),
    (r"\b(json only|only json|return only json|only output json)\b", r"\b(explain|commentary|rationale|with an explanation|add notes)\b",
     "The prompt asks for JSON only but also requests explanations."),
]
NEGATION_PREFIX = r"(?:do not|don't|dont|no|without|avoid|never|not)\s+(?:use\s+|using\s+|include\s+|add\s+|any\s+|a\s+|an\s+)*"
FORMAT_WORDS = {"table": r"tables?", "bullet points": r"bullet(?:ed)?(?: points?| lists?)?s?", "headings": r"headings?",
                "code blocks": r"code blocks?", "markdown": r"markdown"}
PRIVACY_PATTERNS = [
    ("Email address", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", "high"),
    ("Possible phone number", r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3,5}\)?[\s.-]?)\d{3,4}[\s.-]?\d{3,4}(?!\d)", "medium"),
    ("Possible card or account number", r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)", "high"),
    ("Possible national ID (SSN/Aadhaar style)", r"(?<!\d)(?:\d{3}-\d{2}-\d{4}|\d{4}\s\d{4}\s\d{4})(?!\d)", "high"),
    ("Possible PAN / tax ID", r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "high"),
    ("IP address", r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "medium"),
    ("Credential-like text", r"\b(?:password|passcode|passwd|api[_ -]?key|secret|token)\s*[:=]\s*\S+", "high"),
    ("Sensitivity keyword", r"\b(?:confidential|internal only|do not distribute|patient|medical record|diagnosis|ssn|social security|salary of|payroll)\b", "medium"),
]


# --------------------------------------------------------------------------- helpers
def _words(text: str) -> list[str]:
    return re.findall(r"[\w'’\-]+", text.lower(), flags=re.UNICODE)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p and p.strip()]


def parse_sections(text: str) -> dict[str, str]:
    """Parse 'Label: text' blocks (Role:, Context:, Task: ...) into canonical keys."""
    sections: dict[str, str] = {}
    current: str | None = None
    for line in (text or "").splitlines():
        m = _SECTION_RE.match(line)
        if m:
            current = _LABEL_TO_KEY[m.group(1).lower()]
            sections[current] = (sections.get(current, "") + "\n" + m.group(2)).strip()
        elif current and line.strip():
            sections[current] = (sections[current] + "\n" + line.strip()).strip()
        elif not line.strip():
            continue
    return {k: v for k, v in sections.items() if v.strip()}


def _section_strength(body: str | None) -> float:
    if not body:
        return 0.0
    n = len(_words(body))
    if n < 2:
        return 0.2
    return min(1.0, 0.65 + n * 0.035)


def _count(patterns: list[str], text: str) -> int:
    return sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))


# --------------------------------------------------------------------------- analysis
@dataclass
class Component:
    key: str
    strength: float = 0.0
    evidence: str = ""
    clarify: str = ""

    @property
    def status(self) -> str:
        if self.strength >= 0.65:
            return "needs_clarification" if self.clarify else "present"
        if self.strength >= 0.2:
            return "needs_clarification" if self.clarify else "partial"
        return "missing"


@dataclass
class Analysis:
    text: str
    components: dict[str, Component] = field(default_factory=dict)
    sections: dict[str, str] = field(default_factory=dict)
    words: int = 0
    vague_terms: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    privacy: list[dict] = field(default_factory=list)
    task_sentence: str = ""
    use_case: str = "general"


def analyze_text(text: str, use_case: str | None = None) -> Analysis:
    text = (text or "").strip()
    low = text.lower()
    words = _words(text)
    sections = parse_sections(text)
    a = Analysis(text=text, sections=sections, words=len(words))
    a.use_case = use_case if use_case and use_case != "auto" else detect_use_case(text)
    sents = _sentences(text)

    # ---- ambiguity --------------------------------------------------------
    for term in VAGUE:
        if re.search(r"\b" + re.escape(term) + r"\b", low):
            a.vague_terms.append(term)
    if len(words) <= 10 and re.search(r"\b(it|this|that|these|those)\b", low) and not sections:
        a.vague_terms.append("unclear reference (it/this/that)")

    # ---- task ------------------------------------------------------------------
    best = (0, "")
    for s in sents:
        toks = _words(s)
        head = toks[:7]
        has_verb = any(t in ACTION_VERBS for t in head) or (toks[:1] and toks[0] in QUESTION_STARTS and s.endswith("?"))
        if has_verb:
            content = [t for t in toks if t not in STOPWORDS and t not in ACTION_VERBS]
            if len(content) >= best[0]:
                best = (len(content), s)
    task = Component("task")
    if "task" in sections:
        task.strength = _section_strength(sections["task"])
        task.evidence = sections["task"].split("\n")[0][:140]
        a.task_sentence = sections["task"]
    elif best[1]:
        n_content = best[0]
        deliverable = any(w in DELIVERABLES for w in _words(best[1]))
        connectors = bool(re.search(r"\b(including|covering|that|which|focusing|focus on|based on|so that|with|for|about|on)\b", best[1].lower()))
        s = 0.3 + min(0.4, n_content * 0.045) + (0.2 if deliverable else 0.0) + (0.1 if connectors and n_content >= 4 else 0.0)
        task.strength = min(1.0, s)
        task.evidence = best[1][:140]
        a.task_sentence = best[1]
    elif any(w in DELIVERABLES for w in words):
        task.strength = 0.15
        task.evidence = "A deliverable is named but no clear action verb was found."
    a.components["task"] = task
    if task.strength >= 0.2 and a.vague_terms and (not sections.get("task")):
        task.clarify = "The task contains vague wording (" + ", ".join(a.vague_terms[:3]) + ")."

    # ---- role ----------------------------------------------------------------
    role = Component("role")
    if "role" in sections:
        role.strength = max(_section_strength(sections["role"]), 0.7)
        role.evidence = sections["role"].split("\n")[0][:120]
    else:
        m = re.search(r"\b(act as|acting as|you are|you're|take on the role of|play the role of|pretend to be|behave as|as an?)\s+(?:an? |the )?([^.,\n]{3,80})", text, re.IGNORECASE)
        if m:
            phrase = m.group(2).lower()
            lead = m.group(1).lower()
            has_noun = any(re.search(r"\b" + n + r"\b", phrase) for n in ROLE_NOUNS)
            if lead == "as an?" or lead.startswith("as a"):
                role.strength = 0.8 if has_noun else 0.0
            elif has_noun:
                role.strength = 1.0 if len(phrase.split()) >= 3 else 0.75
            else:
                role.strength = 0.35 if re.search(r"helpful|assistant|ai\b|bot", phrase) else 0.5
            if role.strength:
                role.evidence = m.group(0)[:120]
    a.components["role"] = role

    # ---- context ---------------------------------------------------------------
    ctx = Component("context")
    if "context" in sections:
        ctx.strength = _section_strength(sections["context"])
        ctx.evidence = sections["context"].split("\n")[0][:140]
    else:
        groups = sum(1 for p in CONTEXT_CUES.values() if re.search(p, low))
        domain = min(3, len(set(re.findall(DOMAIN_NOUNS, low))))
        info_sents = [s for s in sents if len(_words(s)) >= 6 and s != a.task_sentence
                      and not re.match(r"\s*(please\s+)?(" + "|".join(sorted(ACTION_VERBS)) + r")\b", s.lower())]
        strength = 0.28 * groups + 0.18 * min(2, len(info_sents)) + 0.07 * domain
        if len(words) < 8:
            strength = min(strength, 0.15)
        ctx.strength = min(1.0, strength)
        if ctx.strength:
            ctx.evidence = (info_sents[0] if info_sents else "Some background cues were found.")[:140]
    a.components["context"] = ctx

    # ---- input ------------------------------------------------------------------
    inp = Component("input")
    if "input" in sections:
        inp.strength = _section_strength(sections["input"])
        inp.evidence = sections["input"].split("\n")[0][:140]
    else:
        placeholders = len(re.findall(r"\[[^\]\n]{2,60}\]|\{\{[^}]+\}\}|<[A-Za-z][^>]{2,40}>", text))
        pointer = bool(re.search(r"\b(below|following|attached|pasted|provided|here is|here are|as follows|based on|using the|from the (?:text|data|notes|document))\b", low))
        delim = bool(re.search(r"```|\"\"\"|<<<|^-{3,}|^#{2,}", text, re.MULTILINE))
        long_after_colon = bool(re.search(r":\s*\n?.{80,}", text, re.DOTALL)) and len(words) > 25
        quoted = bool(re.search(r"[\"“][^\"”]{25,}[\"”]", text))
        numbers = len(re.findall(r"\b\d[\d,.]*\b", text))
        strength = (0.4 if pointer else 0) + (0.4 if placeholders else 0) + (0.2 if placeholders > 1 else 0) \
            + (0.3 if delim else 0) + (0.3 if long_after_colon else 0) + (0.3 if quoted else 0) + (0.15 if numbers >= 3 else 0)
        inp.strength = min(1.0, strength)
        if inp.strength:
            inp.evidence = "Input cues found (placeholders, delimiters or references to supplied text)."
    a.components["input"] = inp

    # ---- output format ----------------------------------------------------------
    out = Component("output_format")
    if "output_format" in sections:
        out.strength = _section_strength(sections["output_format"])
        out.evidence = sections["output_format"].split("\n")[0][:140]
    else:
        n_struct = _count(FORMAT_STRUCT_CUES, low)
        deliverable = any(w in DELIVERABLES for w in words)
        strength = (0.3 if deliverable else 0) + min(3, n_struct) * 0.25
        if re.search(r"\b(format|structure|layout)\b", low) and n_struct:
            strength += 0.1
        if re.search(r"\b\d+\s*(slides?|bullets?|bullet points|sentences?|paragraphs?|rows?|columns?|sections?|items?|steps?)\b", low):
            strength += 0.15
        out.strength = min(1.0, strength)
        if out.strength:
            out.evidence = "Deliverable/format cues: " + ", ".join(sorted({w for w in words if w in DELIVERABLES})[:3] or ["format keywords"])
    a.components["output_format"] = out

    # ---- constraints ------------------------------------------------------------
    con = Component("constraints")
    if "constraints" in sections:
        con.strength = _section_strength(sections["constraints"])
        con.evidence = sections["constraints"].split("\n")[0][:140]
    else:
        n = _count(CONSTRAINT_CUES, low)
        con.strength = min(1.0, n * 0.3)
        if n:
            con.evidence = f"{n} constraint cue(s) found (limits, exclusions or requirements)."
    a.components["constraints"] = con

    # ---- audience ---------------------------------------------------------------
    aud = Component("audience")
    nouns = "|".join(sorted(set(AUDIENCE_NOUNS), key=len, reverse=True))
    if "audience" in sections:
        aud.strength = max(0.8, _section_strength(sections["audience"]))
        aud.evidence = sections["audience"].split("\n")[0][:120]
    elif re.search(r"\b(audience|readers?|target group|aimed at|written for|intended for)\b", low):
        aud.strength = 0.85
        aud.evidence = "The audience is mentioned."
    elif re.search(r"\bfor (?:the |our |my |a |an )?(?:[\w-]+ )?(" + nouns + r")\b", low) or re.search(r"\bto (?:the |our |my |a )?(?:senior |executive |project )?(" + nouns + r")\b", low):
        aud.strength = 0.75
        aud.evidence = "A reader group is named."
    elif re.search(r"\b(?:to|for) (?:my|the|our|a) \w+", low):
        aud.strength = 0.3
        aud.evidence = "A recipient is implied but not described."
    a.components["audience"] = aud

    # ---- tone ---------------------------------------------------------------------
    tone = Component("tone")
    if "tone" in sections:
        tone.strength = max(0.8, _section_strength(sections["tone"]))
        tone.evidence = sections["tone"].split("\n")[0][:100]
    else:
        found = [w for w in TONE_WORDS if re.search(r"\b" + re.escape(w) + r"\b", low)]
        if found:
            tone.strength = 1.0 if re.search(r"\b(tone|voice|style)\b", low) else 0.8
            tone.evidence = "Tone words: " + ", ".join(found[:3])
        elif re.search(r"\b(tone|voice|style)\b", low):
            tone.strength = 0.4
            tone.evidence = "Tone is mentioned but not defined."
    a.components["tone"] = tone

    # ---- quality criteria -----------------------------------------------------------
    q = Component("quality_criteria")
    if "quality_criteria" in sections:
        q.strength = _section_strength(sections["quality_criteria"])
        q.evidence = sections["quality_criteria"].split("\n")[0][:140]
    else:
        n = _count(QUALITY_CUES, low)
        q.strength = min(1.0, n * 0.4)
        if n:
            q.evidence = f"{n} quality expectation cue(s) found."
    a.components["quality_criteria"] = q

    # ---- specificity ------------------------------------------------------------------
    n = len(words)
    base = 0 if n < 5 else 0.15 if n < 15 else 0.35 if n < 30 else 0.55 if n < 60 else 0.75 if n < 150 else 0.85
    nums = min(0.1, len(re.findall(r"\b\d+\b", text)) * 0.03)
    names = min(0.1, len(re.findall(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}\b", text)) * 0.03)
    structure = 0.1 if len(sections) >= 4 else 0.0
    spec = Component("specificity", min(1.0, base + nums + names + structure))
    spec.evidence = f"{n} words; {len(sections)} labelled section(s)."
    if a.vague_terms and len(a.vague_terms) / max(n, 1) > 0.05:
        spec.clarify = "Vague wording lowers specificity."
    a.components["specificity"] = spec

    # ---- clarifications ---------------------------------------------------------------
    a.conflicts = _find_conflicts(low)
    if a.conflicts:
        out.clarify = out.clarify or ("Conflicting instructions detected." if out.strength >= 0.2 else "")
        con.clarify = con.clarify or ("Conflicting instructions detected." if con.strength >= 0.2 else "")
    a.privacy = _privacy_scan(text)
    return a


def _find_conflicts(low: str) -> list[str]:
    found = []
    for a_pat, b_pat, msg in CONFLICT_PAIRS:
        if re.search(a_pat, low) and re.search(b_pat, low):
            found.append(msg)
    # word limit vs minimum
    maxs = [int(n) for n in re.findall(r"(?:under|below|no more than|at most|maximum(?: of)?|max\.?|within|up to)\s+(\d+)\s+words", low)]
    mins = [int(n) for n in re.findall(r"(?:at least|minimum(?: of)?|no fewer than|more than|over)\s+(\d+)\s+words", low)]
    if maxs and mins and min(maxs) < max(mins):
        found.append(f"The word limit (max {min(maxs)}) is lower than the required minimum ({max(mins)} words).")
    # negated format vs requested format
    for name, pat in FORMAT_WORDS.items():
        neg = re.search(NEGATION_PREFIX + pat + r"\b", low)
        if neg:
            stripped = re.sub(NEGATION_PREFIX + pat + r"\b", " ", low)
            if re.search(r"\b(?:as|in|use|using|with|provide|return|format(?:ted)? as)\s+(?:an?\s+)?" + pat + r"\b", stripped):
                found.append(f"The prompt both requires and forbids {name}.")
    # exactly N vs exactly M of the same unit
    by_unit: dict[str, set[str]] = {}
    for n, unit in re.findall(r"\bexactly\s+(\d+)\s+(\w+)", low):
        by_unit.setdefault(unit.rstrip("s"), set()).add(n)
    for unit, nums in by_unit.items():
        if len(nums) > 1:
            found.append(f"The prompt asks for exactly {' and '.join(sorted(nums))} {unit}s.")
    return found


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def _privacy_scan(text: str) -> list[dict]:
    """Return privacy indicators WITHOUT echoing the detected values."""
    out = []
    for label, pattern, severity in PRIVACY_PATTERNS:
        flags = 0 if "PAN" in label else re.IGNORECASE
        matches = list(re.finditer(pattern, text, flags))
        if label.startswith("Possible card"):
            matches = [m for m in matches if _luhn(re.sub(r"\D", "", m.group(0))) and len(re.sub(r"\D", "", m.group(0))) >= 13]
        if label.startswith("Possible phone"):
            matches = [m for m in matches if 9 <= len(re.sub(r"\D", "", m.group(0))) <= 13 and not re.fullmatch(r"\d{4}", m.group(0).strip())
                       and re.search(r"[\s+().-]", m.group(0).strip())]
        if label == "IP address":
            matches = [m for m in matches if all(int(p) <= 255 for p in m.group(0).split("."))]
        if matches:
            out.append({"type": label, "severity": severity, "count": len(matches),
                        "message": f"{label} detected ({len(matches)}). Remove or anonymise it before sending the prompt to any AI tool."})
    return out


# --------------------------------------------------------------------------- scoring
class ScoringService:
    """Scores a prompt 0-100 and produces a transparent breakdown."""

    def analyze(self, text: str, use_case: str | None = None) -> dict:
        a = analyze_text(text, use_case)
        profile = get_profile(a.use_case)
        breakdown = []
        total = 0
        for key, label, max_pts in WEIGHTS:
            comp = a.components[key]
            pts = round(max_pts * comp.strength)
            total += pts
            breakdown.append({"key": key, "label": label, "max": max_pts, "points": pts, "status": comp.status,
                              "note": comp.evidence or "Not found in the prompt."})
        adjustments = []
        # ambiguity
        if a.vague_terms and a.words:
            density = len(a.vague_terms) / max(a.words, 1)
            if density > 0.03 or a.words < 15:
                pen = -min(6, max(1, round(len(a.vague_terms) * 1.5)))
                adjustments.append({"label": "Ambiguous wording", "points": pen,
                                    "reason": "Vague terms found: " + ", ".join(a.vague_terms[:5]) + "."})
        for c in a.conflicts[:2]:
            adjustments.append({"label": "Conflicting instructions", "points": -5, "reason": c})
        if a.words > 1200:
            adjustments.append({"label": "Very long prompt", "points": -3,
                                "reason": "Prompts over ~1,200 words are hard to follow; split the task or move reference material into a separate input."})
        total += sum(x["points"] for x in adjustments)
        if a.words < 4:
            cap = 25
            if total > cap:
                adjustments.append({"label": "Extremely short prompt", "points": cap - total,
                                    "reason": "Prompts under 4 words cannot carry enough information; score capped at 25."})
                total = cap
        score = max(0, min(100, total))
        label = readiness_label(score)

        strengths, missing, suggestions = [], [], []
        for key in DIAGNOSTIC_ORDER:
            comp = a.components[key]
            name = LABELS[key]
            if comp.status == "present":
                strengths.append(f"{name} is clearly defined.")
            elif comp.status in ("partial", "needs_clarification"):
                missing.append(f"{name} is only partly defined." if comp.status == "partial" else f"{name} needs clarification.")
                suggestions.append(self._recommendation(key, comp, profile))
            elif key != "tone" or score < 80:
                missing.append(f"{name} is missing.")
                suggestions.append(self._recommendation(key, comp, profile))
        for c in a.conflicts:
            suggestions.append("Resolve the conflict: " + c)
        if a.vague_terms:
            suggestions.append("Replace vague wording (" + ", ".join(a.vague_terms[:4]) + ") with concrete details, numbers or examples.")
        if a.privacy:
            suggestions.append("Remove or anonymise sensitive data before using this prompt with an AI tool.")
        seen = set()
        suggestions = [s for s in suggestions if not (s in seen or seen.add(s))]
        return {
            "score": score, "label": label, "max": 100,
            "breakdown": breakdown, "adjustments": adjustments,
            "strengths": strengths, "missing": missing, "suggestions": suggestions,
            "conflicts": a.conflicts, "vague_terms": a.vague_terms, "privacy": a.privacy,
            "use_case": a.use_case, "use_case_label": profile["label"],
            "stats": {"words": a.words, "sections_found": sorted(a.sections.keys())},
            "components": [self._component_dict(a, k, profile) for k in DIAGNOSTIC_ORDER],
        }

    @staticmethod
    def _component_dict(a: Analysis, key: str, profile: dict) -> dict:
        c = a.components[key]
        rec = ScoringService._recommendation(key, c, profile) if c.status != "present" else ""
        return {"key": key, "label": LABELS[key], "status": c.status, "strength": round(c.strength, 2),
                "evidence": c.evidence, "clarification": c.clarify, "recommendation": rec}

    @staticmethod
    def _recommendation(key: str, comp: Component, profile: dict) -> str:
        recs = profile.get("recs", {})
        generic = {
            "role": "Define who the AI should act as (for example: \"Act as a senior business analyst\").",
            "context": "Explain the topic and the business context.",
            "task": "State one clear task with an action verb and a defined deliverable.",
            "input": "Provide the source information the answer must be based on (paste it or use a [PLACEHOLDER]).",
            "output_format": "Specify the output format (table, bullets, sections, email, JSON...).",
            "constraints": "Add constraints such as length, scope, exclusions and things to avoid.",
            "audience": "State the intended audience.",
            "tone": "Add the tone you want (for example professional and concise).",
            "quality_criteria": "Define quality criteria: how to judge a good answer and what to do when information is missing.",
            "specificity": "Add concrete details: numbers, names, dates, examples and limits.",
        }
        if key == "task" and comp.status in ("partial", "needs_clarification"):
            return "Make the task more specific: say exactly what to produce, about what, and what it should include."
        if key == "task" and comp.status == "missing":
            return generic["task"]
        return recs.get(key) or generic[key]

    def diagnose(self, text: str, use_case: str | None = None) -> dict:
        """Diagnostic view: per-component status, privacy indicators and recommendations."""
        result = self.analyze(text, use_case)
        profile = get_profile(result["use_case"])
        extra = []
        recs = [c["recommendation"] for c in result["components"] if c["recommendation"] and c["key"] != "specificity"]
        if result["stats"]["words"] < 4 and result["use_case"] != "general":
            extra.append(f"Describe the {profile['label'].lower()} in more detail so the AI knows what you need.")
        # order recommendations by importance (breakdown weight)
        result["recommendations"] = recs + extra + [s for s in result["suggestions"] if s not in recs and not s.startswith(tuple(r[:15] for r in recs))]
        seen = set()
        result["recommendations"] = [r for r in result["recommendations"] if r and not (r in seen or seen.add(r))]
        result["risk_checks"] = [
            {"key": "ambiguity", "label": "Ambiguity",
             "status": "needs_clarification" if result["vague_terms"] else "present",
             "summary": ("Vague wording found: " + ", ".join(result["vague_terms"][:6]) + ".") if result["vague_terms"] else "No vague wording detected."},
            {"key": "conflicts", "label": "Conflicting instructions",
             "status": "needs_clarification" if result["conflicts"] else "present",
             "summary": " ".join(result["conflicts"]) if result["conflicts"] else "No conflicting instructions detected."},
            {"key": "privacy", "label": "Privacy risk indicators",
             "status": "needs_clarification" if result["privacy"] else "present",
             "summary": ("Possible sensitive data detected (" + ", ".join(sorted({p.get("type", "item") for p in result["privacy"]})) + "). Remove or anonymise it.")
             if result["privacy"] else "No obvious sensitive data detected (this check is not exhaustive)."},
        ]
        return result


scoring_service = ScoringService()
