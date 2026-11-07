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
    other = {"Task-3": {"0": {"link": "https://t/x", "option": "Fixed", "taskID": "3"}}}
    assert newest_links(other, "12") == {}
    assert newest_links(None, "12") == {}
