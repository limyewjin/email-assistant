import io
from contextlib import redirect_stdout, redirect_stderr

def execute_python_code(code, globals={}):
    """
    Executes a given Python code string and returns the standard output and error as strings.

    Args:
        code (str): A string containing Python code to be executed.

    Returns:
        tuple: A tuple containing the standard output (stdout) and standard error (stderr) as strings.
    """
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exec(code, globals)
    except Exception as e:
        return None, str(e)
    return stdout_buffer.getvalue(), stderr_buffer.getvalue()
