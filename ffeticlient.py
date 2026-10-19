import subprocess
import re

class FFEtiClient():
    STATUS_REGEX = re.compile(r"^\{(?P<status>OK|ERROR|PASS|FAIL|INFO)\}")

    def __init__(self):
        self.last_status = None
        self.last_raw_message = None

    def send_results_to_FF(self, serial_no, ffeti_config_file, parameters="", action=""):
        _debug = True
        eti_client_path = r"C:\ffeti\ffeticlient.exe"
        initfile_path = rf"C:\ffeti\{ffeti_config_file}"

        eti_command = f"{eti_client_path} -config:{initfile_path} {action} {parameters} {serial_no}"

        if _debug:
            print(f"Eti command : {eti_command}\n")

        result = subprocess.run(
            eti_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        self.last_raw_message = result.stdout
        self.last_status = self._parse_status(result.stdout)

        return result.stdout

    def _parse_status(self, message: str):
        if not message:
            return None

        match = self.STATUS_REGEX.search(message)
        if match:
            return match.group("status")

        return None