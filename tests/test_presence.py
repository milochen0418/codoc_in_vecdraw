"""Who is on which drawing."""

from codoc_in_vecdraw import presence


def setup_function():
    presence._rooms.clear()


def test_people_get_their_own_colours():
    _, a = presence.join("d", "t1", "p1", "a", "Ann", now=0)
    _, b = presence.join("d", "t2", "p2", "b", "Bob", now=0)
    assert a != b
    assert [t["name"] for t in presence.tabs("d")] == ["Ann", "Bob"]


def test_two_tabs_of_one_person_are_one_colour_and_one_person():
    _, first = presence.join("d", "t1", "p1", "a", "Ann", now=0)
    _, second = presence.join("d", "t2", "p2", "a", "Ann", now=0)
    assert first == second
    assert presence.users_on("d") == ["a"]
    assert len(presence.watching()["d"]) == 1


def test_leaving_and_going_silent():
    presence.join("d", "t1", "p1", "a", "Ann", now=0)
    presence.join("d", "t2", "p2", "b", "Bob", now=0)
    assert presence.leave("t1") == "d"
    assert presence.prune("d", idle=30, now=31) == ["t2"]
    assert presence.tabs("d") == []


def test_a_tab_is_on_one_drawing():
    presence.join("d", "t1", "p1", "a", "Ann", now=0)
    left, _ = presence.join("e", "t1", "p1", "a", "Ann", now=0)
    assert left == "d" and presence.tabs("d") == []


def test_initials():
    assert presence.initials("Guest 1011") == "G1"
    assert presence.initials("") == "?"
