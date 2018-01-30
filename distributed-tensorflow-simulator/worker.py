from entity import Entity

class Worker (Entity):
    def __init__(self, ctx, name="Worker", model_name='inception-v3', inbuffer_size=0, fwd_pass_time=0, use_multicast=0):
        Entity.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
        self.received_packets = 0
        self.fwd_pass_time = fwd_pass_time
        self.first_layer_received = 0
        self.model_name = model_name
        self.use_multicast = use_multicast

    def lastbitrecv(self, packet):
        Entity.lastbitrecv(self, packet)
        node_name = self.name

        first_layer_dict = {'inception-v3':  'conv0/weights/read',
                            'resnet-200': 'resnet_v2_200/block3/unit_9/bottleneck_v2/conv3/kernel/Regularizer/l2_regularizer',
                            'resnet-101': 'resnet_v2_101/conv1/weights/read',
                            'vgg16': 'conv0/weights/read'
                            }

        raw_nodename = node_name
        if self.use_multicast == 1:
            split_keyword = '_ps'
            raw_nodename = node_name.split(split_keyword)[0]
        
        if raw_nodename == first_layer_dict[self.model_name]:
            self.first_layer_received = self.ctx.now
        
        if not packet.MF:
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
                    print 'Worker {} waiting until at least {} for forward pass to complete'.format(self.name, send_at)
                    for arr in self.ctx.sendschedule[node_name]:
                        time_delta = send_at + arr[0] - self.ctx.now
                        self.ctx.schedule_send(time_delta, arr[1], self.name, arr[2], name=arr[3])
                    
