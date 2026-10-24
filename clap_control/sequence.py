class Sequence:
    def __init__(self, count=2, interval=0.8, cooldown=3.0):
        self.count = count
        self.interval = interval
        self.cooldown = cooldown
        self.pending = 0
        self.last = float("-inf")
        self.blocked_until = float("-inf")

    def clap(self, now):
        if now < self.blocked_until or now - self.last < 0.18:
            return False
        if now - self.last > self.interval:
            self.pending = 0
        self.last = now
        self.pending += 1
        if self.pending == self.count:
            self.pending = 0
            self.blocked_until = now + self.cooldown
            return True
        return False
