"""Tests for the reproducibility core (RNG sub-streams + canonical hashing)."""

from matss.determinism import RandomSource, state_hash, hash_events, canonical_json


def test_rng_same_seed_reproducible():
    a = RandomSource(42)
    b = RandomSource(42)
    seq_a = [a.stream("movement").random() for _ in range(100)]
    seq_b = [b.stream("movement").random() for _ in range(100)]
    assert seq_a == seq_b


def test_rng_streams_independent_of_order():
    # Drawing from another stream first must not perturb 'movement'.
    a = RandomSource(7)
    a.stream("social").random()
    a.stream("spawn").randint(0, 1000)
    first_move = a.stream("movement").random()

    b = RandomSource(7)
    direct_move = b.stream("movement").random()
    assert first_move == direct_move


def test_rng_memoised_same_object():
    rs = RandomSource(1)
    assert rs.stream("x") is rs.stream("x")


def test_rng_different_seeds_differ():
    assert RandomSource(1).stream("x").random() != RandomSource(2).stream("x").random()


def test_fork_is_deterministic_and_isolated():
    parent = RandomSource(99)
    f1 = parent.fork("alex").stream("move").random()
    f2 = RandomSource(99).fork("alex").stream("move").random()
    assert f1 == f2
    assert parent.fork("alex").stream("m").random() != parent.fork("bella").stream("m").random()


def test_state_hash_key_order_invariant():
    assert state_hash({"a": 1, "b": 2}) == state_hash({"b": 2, "a": 1})


def test_state_hash_float_canonicalisation():
    assert state_hash({"f": 0.1 + 0.2}) == state_hash({"f": 0.3})
    assert state_hash({"f": -0.0}) == state_hash({"f": 0.0})


def test_state_hash_distinguishes_list_and_tuple():
    assert state_hash([1, 2, 3]) != state_hash((1, 2, 3))


def test_state_hash_changes_on_value_change():
    assert state_hash({"x": 1}) != state_hash({"x": 2})


def test_canonical_json_is_stable_string():
    s1 = canonical_json({"b": [3, 2, 1], "a": 0.5})
    s2 = canonical_json({"a": 0.5, "b": [3, 2, 1]})
    assert s1 == s2 and isinstance(s1, str)


def test_hash_events_order_sensitive():
    e1 = {"type": "a", "payload": {"v": 1}}
    e2 = {"type": "b", "payload": {"v": 2}}
    assert hash_events([e1, e2]) != hash_events([e2, e1])


def test_hash_events_chaining():
    e = {"type": "a", "payload": {"v": 1}}
    one = hash_events([e])
    chained = hash_events([e], previous=one)
    assert chained != one
