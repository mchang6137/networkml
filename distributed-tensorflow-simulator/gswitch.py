from switch import Switch

class GSwitch (Switch):
    def __init__(self, ctx, name="GSwitch", inbuffer_size=0):
        Switch.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
