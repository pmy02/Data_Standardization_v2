from menunorm.tokenize import SimpleTokenizer, filter_tokens, remove_stopwords


def test_span_stopword_removal_over_full_sequence():
    # MeCab splits 시그니처 into 시그/니/처 where 니 is tagged as a copula;
    # span matching must run before the POS filter to re-join it.
    pairs = [("시그", "NNP"), ("니", "VCP+EC"), ("처", "NNG"), ("로제", "NNG"), ("파스타", "NNG")]
    assert filter_tokens(pairs, {"시그니처"}) == ["로제", "파스타"]


def test_pos_filter_drops_particles_and_endings():
    pairs = [("아메리카노", "NNG"), ("와", "JC"), ("크로플", "NNP")]
    assert filter_tokens(pairs, set()) == ["아메리카노", "크로플"]


def test_remove_stopwords_token_and_span_level():
    assert remove_stopwords(["아메리카노", "세트"], {"세트"}) == ["아메리카노"]
    assert remove_stopwords(["단", "품", "김밥"], {"단품"}) == ["김밥"]
    # Substrings inside a longer single token are never touched.
    assert remove_stopwords(["대왕카스테라"], {"대"}) == ["대왕카스테라"]


def test_simple_tokenizer_analyze_tags_everything_as_noun():
    assert SimpleTokenizer().analyze("치즈 돈가스") == [("치즈", "NNG"), ("돈가스", "NNG")]
