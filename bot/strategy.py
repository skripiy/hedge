class Strategy:
    def __init__(self, exchange_manager_a, exchange_manager_b):
        self.ex_a = exchange_manager_a
        self.ex_b = exchange_manager_b
    
    async def check_opportunity(self):
        # Placeholder for strategy logic
        pass

    async def execute(self):
        # Placeholder for execution logic
        pass
