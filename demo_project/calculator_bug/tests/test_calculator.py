from calculator import calculate_average


def test_average_normal():
    assert calculate_average([10, 20, 30]) == 20


def test_average_empty():
    assert calculate_average([]) == 0