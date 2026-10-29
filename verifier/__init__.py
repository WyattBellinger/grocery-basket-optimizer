"""NanoAgent's deterministic verifier entrypoints; no runtime implementation imports."""

from .basket import check_input, check_result, verdict


def verify_input(tool, value):
    if tool != "optimize_basket":
        return verdict(False, "unknown tool")
    return check_input(value)


def verify_output(tool, input_value, output_value, workspace):
    if tool != "optimize_basket":
        return verdict(False, "unknown tool")
    return check_result(input_value, output_value)


def verify_task(task, arguments, output, reference, workspace):
    if task != "optimize-grocery-basket":
        return verdict(False, "unknown task")
    return check_result(arguments, output)
