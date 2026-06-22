from core import ComparisonOperator, LogicMode, TradingQuery


def check_query(query: TradingQuery, prices: dict[str, float]) -> bool:
    """
    Evaluates every condition in query.conditions against the prices dict
    (ticker -> current price), then combines the results according to
    query.logic (AND = all must hold, OR = at least one must hold).

    Fail-safe: if a condition's ticker is missing from `prices`, that
    condition evaluates to False (do not raise an exception for a missing
    ticker).
    """
    results: list[bool] = []

    for condition in query.conditions:
        actual = prices.get(condition.ticker)
        if actual is None:
            results.append(False)
            continue

        match condition.operator:
            case ComparisonOperator.GREATER_THAN:
                results.append(actual > condition.value)
            case ComparisonOperator.LESS_THAN:
                results.append(actual < condition.value)
            case ComparisonOperator.GREATER_OR_EQUAL:
                results.append(actual >= condition.value)
            case ComparisonOperator.LESS_OR_EQUAL:
                results.append(actual <= condition.value)
            case ComparisonOperator.EQUAL:
                results.append(actual == condition.value)

    if query.logic == LogicMode.AND:
        return all(results)
    return any(results)
