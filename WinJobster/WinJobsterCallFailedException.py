class WinJobsterCallFailedException(Exception):
    def __init__(self, error_code):
        self.error_code = error_code
        self.message = 'WinJobster call failed'

        super().__init__(self.message, self.error_code)
