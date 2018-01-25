from entity import Entity

class GSwitch (Entity):
    def __init__(self, ctx, name="GSwitch", inbuffer_size=0):
        Entity.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
