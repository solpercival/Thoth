from email_sender import send_email, send_notify_email
from email_formatter import format_ezaango_shift_data

def test_1() -> None:
    """
    Send simple email to collector 
    """
    send_notify_email("THIS IS A TEST EMAIL PLEASE DISREGARD", "TESTING")

def test_formatter() -> None:
    test_data:dict = {"intention": "<SHOW>", 
                      "reasoning": "Requested shifts for the date one day from today.", 
                      "staff": {"name": "Adaelia Thomas", "id": "1728", "email": "adaeliathomas@gmail.com"}, 
                      "date_range": {"start_date": "18-12-2025", "end_date": "18-12-2025", "type": "tomorrow"}, 
                      "shifts_found": 1, 
                      "shifts": [{"client": "Zak James", "date": "18-12-2025", "time": "02:00 PM", "shift_id": "207570"}]}
    print(format_ezaango_shift_data(test_data))

def test_2() -> None:
    """
    Send formatted notification email to collector
    """
    test_data:dict = {"intention": "<CNCL>", 
                      "reasoning": "Requested cancellation of shift.", 
                      "staff": {"name": "Adaelia Thomas", "id": "1728", "email": "adaeliathomas@gmail.com"}, 
                      "date_range": {"start_date": "18-12-2025", "end_date": "18-12-2025", "type": "tomorrow"}, 
                      "shifts_found": 1, 
                      "shifts": [{"client": "Zak James", "date": "18-12-2025", "time": "02:00 PM", "shift_id": "207570"}]}
    formatted:str = format_ezaango_shift_data(test_data)

    send_notify_email(formatted, test_data["intention"])

if __name__ == "__main__":
    #test_1()
    test_2()
    #test_formatter()
