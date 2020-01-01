from .switch import Switch

class TOR (Switch):
    def __init__(self, ctx, name="TOR", inbuffer_size=0):
        Switch.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
        