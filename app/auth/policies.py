from app.auth.principal import Principal


def group_allowed(principal: Principal, allowed: frozenset[str]) -> bool:
    return not principal.groups_overage and bool(principal.groups & allowed)
