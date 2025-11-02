from lib.logger import logger

class RingBuffer:
    def __init__(self, capacity: int):
        self.capacity = int(capacity)
        self.buf = bytearray(self.capacity)
        self.start = 0
        self.length = 0

    def __len__(self) -> int:
        return self.length

    def write(self, data: bytes) -> int:
        n = len(data)
        if n >= self.capacity:
            tail = data[-self.capacity:]
            self.buf[:] = tail
            overflow = self.length
            self.start = 0
            self.length = self.capacity
            logger.debug("RingBuffer.write: full overwrite, overflow=%d", overflow)
            return overflow

        end_pos = (self.start + self.length) % self.capacity
        first = min(n, self.capacity - end_pos)
        self.buf[end_pos:end_pos + first] = data[:first]
        second = n - first
        if second:
            self.buf[0:second] = data[first:first + second]

        new_length = self.length + n
        overflow = max(0, new_length - self.capacity)
        if overflow:
            self.start = (self.start + overflow) % self.capacity
            self.length = self.capacity
            logger.debug("RingBuffer.write: overflow=%d, new_start=%d", overflow, self.start)
        else:
            self.length = new_length

        return overflow

    def read_at(self, rel_offset: int, size: int) -> bytes:
        if rel_offset < 0 or rel_offset >= self.length:
            return b''
        size = min(size, self.length - rel_offset)
        abs_pos = (self.start + rel_offset) % self.capacity
        first = min(size, self.capacity - abs_pos)
        out = bytes(self.buf[abs_pos:abs_pos + first])
        second = size - first
        if second:
            out += bytes(self.buf[0:second])
        return out
