from entity import Entity

class TOR (Entity):
    def __init__(self, ctx, name="TOR", inbuffer_size=0):
        Entity.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)

