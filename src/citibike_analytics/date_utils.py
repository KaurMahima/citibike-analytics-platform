from datetime import date


def month_date_window(year: int, month: int) -> tuple[str, str]:
    start_date = date(year, month, 1)

    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    end_date = date.fromordinal(next_month.toordinal() - 1)
    return start_date.isoformat(), end_date.isoformat()