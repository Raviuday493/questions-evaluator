from app.services.document_parser import DocumentParserService

SAMPLE_PAPER_TEXT = """
SECTION A: MECHANICS

1. Define Newton's First Law of Motion and give a real-world example. (5 marks)

2. A 5kg block is pushed across a frictionless surface with a force of 20N. Calculate acceleration. (10 marks)

3. Explain elastic collisions. (5 marks)

(a) Derive kinetic energy conservation equation. (5 marks)
(b) Calculate velocity after collision. (5 marks)

SECTION B: THERMODYNAMICS

4. State the Second Law of Thermodynamics. (10 marks)
"""


def _by_number(questions):
    return {q.question_number: q for q in questions}


def test_document_parser_regex():
    questions = DocumentParserService.parse_questions_from_text(SAMPLE_PAPER_TEXT)
    qs = _by_number(questions)
    assert set(qs) == {"1", "2", "3", "3(a)", "3(b)", "4"}

    assert qs["1"].section_name == "Section A"
    assert "Newton's First Law" in qs["1"].raw_text
    assert qs["1"].marks == 5
    assert qs["2"].marks == 10
    assert qs["3(a)"].parent_question_number == "3"
    assert qs["3(b)"].marks == 5
    assert qs["4"].section_name == "Section B"
    # Marks annotations are stripped from the clean text used for matching.
    assert "marks" not in qs["2"].clean_text


def test_parent_is_ordered_before_its_sub_questions():
    numbers = [q.question_number for q in DocumentParserService.parse_questions_from_text(SAMPLE_PAPER_TEXT)]
    assert numbers.index("3") < numbers.index("3(a)") < numbers.index("3(b)") < numbers.index("4")


def test_decimals_and_prose_are_not_mistaken_for_questions():
    text = "\n".join([
        "1. A mass of 2 kg moves on a rough surface.",
        "1.5 kg of water is then added to the container.",
        "Hence. the total mass changes. (10 marks)",
        "2. State Hooke's law. (5 marks)",
    ])
    qs = _by_number(DocumentParserService.parse_questions_from_text(text))
    assert set(qs) == {"1", "2"}
    assert "1.5 kg of water" in qs["1"].raw_text
    assert "Hence. the total mass" in qs["1"].raw_text
    assert qs["1"].marks == 10


def test_uppercase_mcq_options_stay_in_the_question_stem():
    text = "\n".join(["Q1. Which quantity is a vector? (1 mark)", "A. Speed", "B. Velocity", "C. Mass", "D. Time"])
    questions = DocumentParserService.parse_questions_from_text(text)
    assert len(questions) == 1
    assert "B. Velocity" in questions[0].raw_text


def test_marks_split_across_wrapped_lines_and_sub_question_continuations():
    text = "\n".join([
        "Question 1: Define entropy and explain why it never decreases in an isolated system. (10",
        "marks)",
        "2. Consider a heat engine.",
        "(a) Draw the PV diagram for one cycle",
        "of the engine. (4 marks)",
        "(ii) Explain the efficiency limit. [3]",
    ])
    qs = _by_number(DocumentParserService.parse_questions_from_text(text))
    assert qs["1"].marks == 10
    assert qs["2(a)"].raw_text.endswith("of the engine. (4 marks)")
    assert qs["2(a)"].marks == 4
    assert qs["2(ii)"].marks == 3


def test_text_without_numbered_questions_yields_nothing():
    assert DocumentParserService.parse_questions_from_text("Just a heading\nand some prose.") == []
