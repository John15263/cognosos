def intervention_planner(decisions):
    return [decision for decision in decisions if getattr(decision, "triggered", False)]

