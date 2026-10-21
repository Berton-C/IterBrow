DESCRIPTION = (
    'Wait without spending tokens. After reporting finished work, wait_seconds=0 waits for new input or '
    'an alarm. For unfinished work or a retry, a positive wait_seconds. Waiting is not failure or '
    'completion.'
)

def run(wait_seconds=0):
    seconds = float(wait_seconds)
    if seconds < 0 or seconds > 86400:
        raise ValueError("wait_seconds must be between 0 and 86400")
    print("NOP")
    return "SUCCESS"
