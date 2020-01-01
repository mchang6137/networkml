from .entity import Entity

class Worker (Entity):
    def __init__(self, ctx, name="Worker", model_name='inception-v3', inbuffer_size=0, fwd_pass_time=0, use_optimal_param=0):
        Entity.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
        self.received_packets = 0
        self.fwd_pass_time = fwd_pass_time
        self.first_layer_received = 0
        self.model_name = model_name
        self.use_optimal_param = use_optimal_param
        self.ready = {}
        self.phase = 0
        self.bits_received = 0
        self.backprop_finish = 0.0
        self.steps_complete = 0

    def queuesend(self, packet): #self.ctx.schedule_task(0.0001, lambda: self.queuesend(packet))
        if self.ctx.butterfly:
            if packet.name not in self.ready:
                if self.ctx.verbosity:
                    print("Gradient {} dropped by {}".format(packet.name, self))
                return
            if packet.degree not in self.ready[packet.name]:
                self.ready[packet.name][packet.degree] = lambda: self.queuesend(packet)
                return
            if self.ready[packet.name][packet.degree] == "ready":
                Entity.queuesend(self, packet)
            if packet.degree + 1 not in self.ready[packet.name]:
                self.ready[packet.name][packet.degree] = "ready"
            elif callable(self.ready[packet.name][packet.degree+1]):
                fun = self.ready[packet.name][packet.degree+1]
                self.ready[packet.name][packet.degree+1] = "ready"
                fun()
            self.ready[packet.name][packet.degree+1] = "ready"
        elif self.ctx.horovod:
            if packet.name not in self.ready:
                self.ready[packet.name] = "ready"
                return
            if callable(self.ready[packet.name]):
                self.ready[packet.name]()
            else:
                Entity.queuesend(self, packet)
        else:
            Entity.queuesend(self, packet)

    def lastbitrecv(self, packet):
        node_name = self.name
        Entity.lastbitrecv(self, packet)

        first_layer_dict = {'inception-v3':  'conv0/weights/read',
                            'inception-v3_alternate': 'conv0/weights/read',
                            'inception-v3_alternate_1': 'conv0/weights/read',
                            'inception-v3_alternate_5': 'conv0/weights/read',
                            'inception-v3_alternate_25': 'conv0/weights/read',
                            'inception-v3_alternate_125': 'conv0/weights/read',
                            'dummy_model': 'layer1',
                            'resnet-200': 'resnet_v2_200/block2/unit_1/bottleneck_v2/conv2/weights/read',
                            'resnet-200_alternate': 'resnet_v2_200/block2/unit_1/bottleneck_v2/conv2/weights/read',
                            'resnet-101': 'resnet_v2_101/conv1/weights/read',
                            'vgg16': 'conv0/weights/read'
                            }

        original_model_name = self.model_name
        if "_extend" in original_model_name:
            original_model_name = original_model_name[:original_model_name.find("_extend")]
        packet_name = packet.name
        if self.use_optimal_param == 1:
            split_keyword = '_ps'
            packet_name = packet_name.split(split_keyword)[0]

        if not packet.MF and packet.name in self.ctx.edge_weights:

            self.bits_received += self.ctx.edge_weights[packet.name]
        
        if ((packet_name == first_layer_dict[original_model_name] and not self.ctx.forward_pass_as_bytes) or
                (self.ctx.forward_pass_as_bytes and self.phase == 0 and self.steps_complete == 0 and
                 self.bits_received >= self.ctx.forward_pass_size) or
                (self.ctx.forward_pass_as_bytes and self.phase == 0 and self.bits_received >= self.ctx.model_size)) \
                and not packet.MF  and not self.ctx.horovod:
            self.first_layer_received = self.ctx.now
            if self.first_layer_received < self.backprop_finish:
                self.first_layer_received = self.backprop_finish
            self.phase = 1
            if self.ctx.verbosity:
                print("%s has received read packet at time %0.3f" % (self.name, self.ctx.now))
        if self.ctx.horovod:
            self.lastbitrecvhorovod(packet)
        elif not packet.MF:
            if self.name == "worker0" and self.ctx.verbosity > 2:
                print((packet.name))
            self.received_packets += 1
            if self.ctx.sendschedule[node_name] and self.received_packets % self.ctx.num_from_ps == 0:
                if self.ctx.verbosity:
                    print("%s has received all gradients at time %0.3f %d" % (self.name, self.ctx.now, self.bits_received))
                self.ctx.worker_receive.append(self.ctx.now)
                # self.received_packets = 0
                self.bits_received = 0
                self.phase = 0
                if self.ctx.now >= self.first_layer_received + self.fwd_pass_time:
                    self.backprop()
                else:
                    send_at = self.first_layer_received + self.fwd_pass_time
                    send_delta = send_at - self.ctx.now
                    if self.ctx.verbosity:
                        print('Worker {} waiting until at least {} for forward pass to complete'.format(self.name, send_at))
                    self.ctx.schedule_task(send_delta, lambda: self.backprop())

    def forwardpasshorovod(self):
        pause = self.fwd_pass_time
        if self.ctx.now + self.fwd_pass_time < self.backprop_finish:
            pause = self.backprop_finish - self.ctx.now
        self.received_packets = 0
        self.bits_received = 0
        self.ctx.schedule_task(pause, lambda: self.backprop())


    def backprop(self):
        if self.ctx.horovod:
            #split = num_workers
            split = 1
            keys = list(self.ctx.pmappings.keys())
            idx = self.ctx.workers.index(self.name)
            nworker = self.ctx.workers[(idx + 1) % len(self.ctx.workers)]
            for arr in self.ctx.sendschedule[self.name]:
                if self.ctx.butterfly:
                    self.ready[arr[3]] = {}
                    self.ready[arr[3]][1] = "ready"
                    nworker = self.ctx.workers[idx + 1 - 2 * (idx % 2)]
                elif (keys.index(arr[3]) % len(self.ctx.workers)) == idx:
                    self.ready[arr[3]] = "root"
                    pass
                time_delta = arr[0]
                self.ctx.schedule_send(time_delta, arr[1] / split, self.name, nworker, name=arr[3])
                self.backprop_finish = self.ctx.now + arr[0]
        else:
            self.steps_complete += 1
            for arr in self.ctx.sendschedule[self.name]:
                self.ctx.schedule_send(arr[0], arr[1], self.name, arr[2], name=arr[3])
                self.backprop_finish = self.ctx.now + arr[0]

    def lastbitrecvhorovod(self, packet):
        if packet.MF:
            return
        if packet.name not in self.ready and not self.ctx.butterfly:
            self.ready[packet.name] = lambda: self.lastbitrecvhorovod(packet)
            return
        elif not self.ctx.butterfly:
            self.ready[packet.name] = "ready"
        idx = self.ctx.workers.index(self.name)
        if packet.degree >= len(self.ctx.workers)-1 and not packet.MF:
            self.received_packets += 1
            if self.received_packets == len(self.ctx.sendschedule[self.name]):
                self.steps_complete += 1
                if self.steps_complete < self.ctx.multi_step:
                    self.forwardpasshorovod()
                if self.steps_complete == 1 and self.ctx.start_time == 0:
                    self.ctx.start_time = self.ctx.now
                if self.steps_complete == self.ctx.multi_step and self.ctx.finish_time == 0:
                    self.ctx.finish_time = self.ctx.now
                if self.ctx.verbosity:
                    print("%s has received all gradients at time %0.3f" % (self.name, self.ctx.now))
        elif 2 ** packet.degree == len(self.ctx.workers) and self.ctx.butterfly and not packet.MF:
            self.received_packets += 1
            if self.received_packets == len(self.ctx.sendschedule[self.name]):
                self.steps_complete += 1
                if self.steps_complete < self.ctx.multi_step:
                    self.forwardpasshorovod()
                if self.steps_complete == 1 and self.ctx.start_time == 0:
                    self.ctx.start_time = self.ctx.now
                if self.steps_complete == self.ctx.multi_step and self.ctx.finish_time == 0:
                    self.ctx.finish_time = self.ctx.now
                if self.ctx.verbosity:
                    print("%s has received all gradients at time %0.3f" % (self.name, self.ctx.now))
            return
        nworker = self.ctx.workers[(idx + 1) % len(self.ctx.workers)]
        if self.ctx.butterfly:
            factor = 2 ** (packet.degree)
            nworker = self.ctx.workers[idx + factor - 2 * ((idx//factor)%2) * factor]
        packet.degree += 1
        if self.ctx.use_multicast and packet.degree == len(self.ctx.workers) and not packet.MF:
            packet.src = self.name
            packet.dest = self.name
            packet.path = self.ctx.paths[packet.src + packet.dest]
            packet.multicast = True
            packet.size = self.ctx.edge_weights[packet.name]
            packet.degree = len(self.ctx.workers) * 2
            self.ctx.schedule_task(0.0001, lambda: self.queuesend(packet))
        elif packet.degree < len(self.ctx.workers) * 2 - 1 and not packet.MF:
            packet = packet.copy()
            packet.src = self.name
            packet.dest = nworker
            packet.path = self.ctx.paths[packet.src + packet.dest]
            packet.size = self.ctx.edge_weights[packet.name]
            self.ctx.schedule_task(0.0001, lambda: self.queuesend(packet))
            
                    
