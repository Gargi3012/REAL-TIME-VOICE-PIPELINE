from app.llm.company_faq import get_faq_context_block, load_faq_data


def test_faq_loads_valid_json():
    data = load_faq_data()
    assert "faqs" in data
    assert "company_name" in data


def test_faq_has_expected_categories():
    data = load_faq_data()
    categories = [section["category"] for section in data["faqs"]]
    assert "About the Company" in categories
    assert "Services" in categories


def test_context_block_contains_company_name():
    block = get_faq_context_block()
    assert "Cybernauts" in block


def test_context_block_contains_fallback_instruction():
    block = get_faq_context_block()
    assert "9990861759" in block or "cybernauts.it" in block


def test_context_block_is_nonempty_string():
    block = get_faq_context_block()
    assert isinstance(block, str)
    assert len(block) > 0