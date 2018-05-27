from entity import Entity

class Worker (Entity):
    def __init__(self, ctx, name="Worker", model_name='inception-v3', inbuffer_size=0, fwd_pass_time=0, use_optimal_param=0):
        Entity.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
        self.received_packets = 0
        self.fwd_pass_time = fwd_pass_time
        self.first_layer_received = 0
        self.model_name = model_name
        self.use_optimal_param = use_optimal_param
        self.ready = set()

    def queuesend(self, packet):
        if self.ctx.horovod and packet.name not in self.ready:
            self.ready.add(packet.name)
            return
        Entity.queuesend(self, packet)

    def lastbitrecv(self, packet):
        node_name = self.name
        Entity.lastbitrecv(self, packet)

        first_layer_dict = {'inception-v3':  'conv0/weights/read',
                            'resnet-200': 'resnet_v2_200/block2/unit_1/bottleneck_v2/conv2/weights/read',
                            'resnet-101': 'resnet_v2_101/conv1/weights/read',
                            'vgg16': 'conv0/weights/read'
                            }

        packet_name = packet.name
        if self.use_optimal_param == 1:
            split_keyword = '_ps'
            packet_name = packet_name.split(split_keyword)[0]
        
        if packet_name == first_layer_dict[self.model_name] and not packet.MF:
            self.first_layer_received = self.ctx.now
            if self.ctx.verbosity:
                print "%s has received read packet at time %0.3f" % (self.name, self.ctx.now)
        if self.ctx.horovod:
            self.lastbitrecvhorovod(packet)
        elif not packet.MF:
            self.received_packets += 1
            if self.ctx.sendschedule[node_name] and self.received_packets == self.ctx.num_from_ps:
                if self.ctx.verbosity:
                    print "%s has received all gradients at time %0.3f" % (self.name, self.ctx.now)
                self.ctx.worker_receive.append(self.ctx.now)
                if self.ctx.now >= self.first_layer_received + self.fwd_pass_time:
                    for arr in self.ctx.sendschedule[node_name]:
                        self.ctx.schedule_send(arr[0], arr[1], self.name, arr[2], name=arr[3])
                else:
                    send_at = self.first_layer_received + self.fwd_pass_time
                    if self.ctx.verbosity:
                        print 'Worker {} waiting until at least {} for forward pass to complete'.format(self.name, send_at)
                    for arr in self.ctx.sendschedule[node_name]:
                        time_delta = send_at + arr[0] - self.ctx.now
                        self.ctx.schedule_send(time_delta, arr[1], self.name, arr[2], name=arr[3])

    def lastbitrecvhorovod(self, packet):
        if packet.name not in self.ready:
            self.ready.add(packet.name)
            return
        idx = self.ctx.workers.index(self.name)
        nworker = self.ctx.workers[(idx + 1) % len(self.ctx.workers)]
        packet.degree += 1
        if packet.degree >= len(self.ctx.workers) and not packet.MF:
            self.received_packets += 1
            if self.received_packets == len(self.ctx.sendschedule[self.name]) and self.ctx.verbosity:
                print "%s has received all gradients at time %0.3f" % (self.name, self.ctx.now)
        if self.ctx.use_multicast and packet.degree == len(self.ctx.workers) and not packet.MF:
            packet.src = self.name
            packet.dest = self.name
            packet.path = self.ctx.paths[packet.src + packet.dest]
            packet.multicast = True
            packet.size = self.ctx.edge_weights[packet.name]
            packet.degree = len(self.ctx.workers) * 2
            self.ctx.schedule_task(0.001, lambda: self.queuesend(packet))
        elif packet.degree < len(self.ctx.workers) * 2 - 1 and not packet.MF:
            packet.src = self.name
            packet.dest = nworker
            packet.path = self.ctx.paths[packet.src + packet.dest]
            packet.size = self.ctx.edge_weights[packet.name]
            self.ctx.schedule_task(0.001, lambda: self.queuesend(packet))
            
                    
