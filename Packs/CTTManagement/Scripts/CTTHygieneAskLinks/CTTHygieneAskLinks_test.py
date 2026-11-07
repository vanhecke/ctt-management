from CTTHygieneAskLinks import newest_links

ONE = {
    "Task-12": {
        "0": {"link": "https://t/f1", "option": "Fixed", "taskID": "12"},
        "1": {"link": "https://t/n1", "option": "Not a violation", "taskID": "12"},
    }
}


def test_newest_links_from_a_single_ask():
    assert newest_links(ONE, "12") == {"fixed_url": "https://t/f1", "not_violation_url": "https://t/n1"}


def test_newest_links_takes_the_latest_round():
    rounds = {
        "Task-12": [
            ONE["Task-12"],
            {
                "0": {"link": "https://t/f2", "option": "Fixed", "taskID": "12"},
                "1": {"link": "https://t/n2", "option": "Not a violation", "taskID": "12"},
            },
        ]
    }
    assert newest_links(rounds, "12") == {"fixed_url": "https://t/f2", "not_violation_url": "https://t/n2"}


def test_newest_links_ignores_other_tasks_and_empty_context():
    assert newest_links({}, "12") == {}


def test_newest_links_in_a_sub_playbook_falls_back_to_the_links_present():
    sub = {
        "Task-11.3": {
            "0": {"link": "https://t/f", "option": "Fixed", "taskID": "11.3"},
            "1": {"link": "https://t/n", "option": "Not a violation", "taskID": "11.3"},
        }
    }
    assert newest_links(sub, "3") == {"fixed_url": "https://t/f", "not_violation_url": "https://t/n"}
    assert newest_links(None, "12") == {}
