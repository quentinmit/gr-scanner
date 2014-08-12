from gnuradio import gr
from gnuradio.filter import firdes, freq_xlating_fir_filter_ccf
from gnuradio.eng_option import eng_option
from gnuradio.gr.pubsub import pubsub
import scanner
import osmosdr
from optparse import OptionParser, OptionGroup
import logging

class SmartnetCmd(object):
    OSW_UNK1 = 0x0273
    OSW_UNK2 = 0x029B
    OSW_UNK3 = 0x02a9
    OSW_UNK4 = 0x02c3
    OSW_UNK5 = 0x0259
    OSW_UNK6 = 0x0279
    OSW_UNK7 = 0x02af
    OSW_BACKGROUND_IDLE = 0x02f8
    OSW_FIRST_CODED_PC = 0x0304
    OSW_FIRST_NORMAL = 0x0308
    OSW_FIRST_TY2AS1 = 0x0309
    OSW_EXTENDED_FCN = 0x030b
    OSW_AFFIL_FCN = 0x030d
    OSW_TY2_AFFILIATION = 0x0310
    OSW_TY1_STATUS_MIN = 0x0310
    OSW_TY2_MESSAGE = 0x0311
    OSW_TY1_STATUS_MAX = 0x0317
    OSW_TY1_ALERT = 0x0318
    OSW_TY1_EMERGENCY = 0x0319
    OSW_TY2_CALL_ALERT = 0x0319
    OSW_SYSTEM_UNK1 = 0x0320
    OSW_FIRST_ASTRO = 0x0321
    OSW_SYSTEM_CLOCK = 0x0322
    OSW_SCAN_MARKER = 0x032b
    OSW_EMERG_ANNC = 0x032e
    OSW_AMSS_ID_MIN = 0x0360
    OSW_AMSS_ID_MAX = 0x039f
    OSW_CW_ID = 0x03a0
    OSW_SYS_NETSTAT = 0x03bf
    OSW_SYS_STATUS = 0x03c0

class smartnet_message(object):
    # Known commands:
    # < 0x2d0 = frequency
    # 0x308 = continuation, addr is "target mobile ID code" (fig 12 in patent)
    def __init__(self, msg, linked, cmd_to_freq = None):
        self.string = msg.to_string()
        self.linked = list(linked)
        [self.addr, self.groupflag, self.cmd] = [int(i) for i in self.string.split(',')]
        self.tg = self.addr & 0xFFF0
        self.prio = self.addr & 0xF
        self.freq = cmd_to_freq and cmd_to_freq(None, self.cmd)

        if self.cmd == SmartnetCmd.OSW_SYS_STATUS:
            value = self.addr << 1 | self.groupflag
            self.group_timeout = value & 0x1f
            value >>= 5
            self.connect_timeout = value & 0x1f
            value >>= 5
            self.dispatch_timeout = value & 0xf
            value >>= 4
            self.power = value & 0x1
            value >>= 1
            self.opcode = value
        elif self.cmd == SmartnetCmd.OSW_SYS_NETSTAT:
            pass
        elif self.cmd == SmartnetCmd.OSW_EXTENDED_FCN:
            pass
    def __str__(self):
        if self.freq:
            return "TALK: Group %04x (Prio %1x) Cmd %03x Frequency %f" % (
                self.tg, self.prio, self.cmd, self.freq)
        elif self.cmd == SmartnetCmd.OSW_SYS_STATUS:
            return "SYS_STATUS: Opcode %1x Power %d Timeouts: Dispatch %ds Connect %ds Group %ds" %(
                self.opcode, self.power,
                self.dispatch_timeout*30,
                self.connect_timeout*30,
                self.group_timeout*30)
        elif self.cmd == SmartnetCmd.OSW_EXTENDED_FCN:
            if (self.addr & 0xfc00) == 0x6000:
                # SmartZone Peer info
                if not self.linked:
                    return "PEER_INFO: MISSING PREFIX PACKET Data %x" % (self.addr & 0x3ff)
                return "PEER_INFO: SysID %04x Data %x" % (self.linked[-1].addr, self.addr & 0x3ff)
            else:
                return "EXTENDED_FCN: %s Addr %04x" % ("Group" if self.groupflag else "Radio", self.addr,)
        else:
            if self.groupflag:
                return "CMD: Radio %04x Cmd %03x" % (self.addr, self.cmd)
            else:
                return "CMD: Group %04x (Prio %1x) Cmd %03x" % (self.tg, self.prio, self.cmd)

class smartnet_all_rx(scanner.smartnet_ctrl_rx):
    def __init__(self, *args, **kwargs):
        scanner.smartnet_ctrl_rx.__init__(self, *args, **kwargs)

        self.linked_cmd = []
    def msg_handler(self, msg):
        msg = smartnet_message(msg, self.linked_cmd, self.cmd_to_freq)
        if msg.cmd == 0x308:
            # Continuation
            self.linked_cmd.append(msg)
        else:
            self.linked_cmd.append(msg)
            if msg.cmd not in (SmartnetCmd.OSW_SYS_STATUS,):
                try:
                    logging.info(", ".join(str(msg) for msg in self.linked_cmd))
                except:
                    logging.exception("Unable to log message")
            self.linked_cmd = []

#instantiates a sample feed, control decoder, audio sink, and control
class trunked_logger(gr.top_block, pubsub):
    def __init__(self, options):
        gr.top_block.__init__(self)
        pubsub.__init__(self)
        self._options = options

        self._source = osmosdr.source()
        wat = self._source.get_sample_rates()
        rate = wat.stop() # Maximum available sample rate
        self._source.set_sample_rate(rate)

        self._source.set_gain(34)

        self._source.set_center_freq(options.center_freq)

        channel_spacing = 25e3

        channel_decimation = int(rate / channel_spacing)

        print "Using channel decimation of %d" % channel_decimation

        taps = firdes.low_pass(1.0,
                               rate,
                               channel_spacing*0.4,
                               channel_spacing*0.1,
                               firdes.WIN_HANN)

        #taps = optfir.low_pass(1.0,
        #                       rate,
        #                       11000,
        #                       12500,
        #                       0.1,
        #                       60)

        self._ctrl_chan = freq_xlating_fir_filter_ccf(channel_decimation,
                                                      taps,
                                                      options.ctrl_freq - options.center_freq,
                                                      rate)

        data_sample_rate = float(rate) / channel_decimation

        print "Using data sample rate of %f" % data_sample_rate

        self._data_path = smartnet_all_rx(data_sample_rate)

        self.connect(self._source, self._ctrl_chan, self._data_path)

        if options.fft:
            pass

    def close(self):
        self._source.close()

    @staticmethod
    def add_options(parser):
        scanner.trunked_feed.add_options(parser)
        group = OptionGroup(parser, "Scanner setup options")
        #Choose source
        group.add_option("-m","--monitor", type="string", default="0",
                        help="Monitor a list of talkgroups (comma-separated) [default=%default]")
        group.add_option("-t","--type", type="string", default="smartnet",
                         help="Network type (edacs or smartnet only) [default=%default]")
        group.add_option("", "--fft", action="store_true", default=False,
                         help="Enable fft plots")
        parser.add_option_group(group)


def main():
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
    logging.info("Starting up")
    #add options to parser
    parser = OptionParser (option_class=eng_option, conflict_handler="resolve")
    trunked_logger.add_options(parser)
    (options, args) = parser.parse_args()

    tb = trunked_logger(options)
    tb.run()
    tb.close()

if __name__ == "__main__":
    main()

