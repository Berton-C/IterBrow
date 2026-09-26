DESCRIPTION = "Wait without spending model tokens. After reporting completed work, use wait_seconds=0 to wait for new input or an alarm. For unfinished work, a retry, or planned autonomous activity, supply a positive wait_seconds; use reminder for scheduled work. Waiting is not failure or task completion."

def run(wait_seconds=0):
    seconds = float(wait_seconds)
    if seconds < 0 or seconds > 86400:
        raise ValueError("wait_seconds must be between 0 and 86400")
    print("NOP")
    return "SUCCESS"
