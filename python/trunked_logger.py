from gnuradio import gr
from gnuradio.filter import firdes, freq_xlating_fir_filter_ccf
from gnuradio.eng_option import eng_option
from gnuradio.gr.pubsub import pubsub
import scanner
import osmosdr
from optparse import OptionParser, OptionGroup
import logging

class smartnet_message(object):
    def __init__(self, msg, cmd_to_freq = None):
        self.string = msg.to_string()
        [self.addr, self.groupflag, self.cmd] = [int(i) for i in self.string.split(',')]
        self.tg = self.addr & 0xFFF0
        self.prio = self.addr & 0xF
        self.freq = cmd_to_freq and cmd_to_freq(None, self.cmd)
    def __str__(self):
        if self.freq:
            return "TALK: Group %04x (Prio %1x) Cmd %03x Frequency %f" % (
                self.tg, self.prio, self.cmd, self.freq)
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
        msg = smartnet_message(msg, self.cmd_to_freq)
        if msg.cmd == 0x308:
            # Continuation
            self.linked_cmd.append(msg)
        else:
            self.linked_cmd.append(msg)
            logging.info(", ".join(str(msg) for msg in self.linked_cmd))
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

