import threading
import unittest
from unittest.mock import Mock, patch
from clap_control.audio import Audio, read_frame


class AudioTests(unittest.TestCase):
    def test_loss_then_reconnect(self):
        stop,restart=threading.Event(),threading.Event()
        process=Mock()
        process.poll.return_value=None
        factory=Mock(side_effect=[OSError('missing microphone'),process,process])
        frames=[]
        status=[]
        reads=0
        def reader(*_):
            nonlocal reads
            reads+=1
            if reads==1: raise OSError('stream lost')
            stop.set()
            return bytes(320)
        audio=Audio(stop,restart,lambda:'test_source',lambda frame,now:frames.append(frame),
                    lambda state,error:status.append(state),factory,reader,0)
        audio.run()
        self.assertEqual(factory.call_count,3)
        self.assertEqual(len(frames),1)
        self.assertEqual(status.count('error'),2)
        self.assertIn('connected',status)
        self.assertIn('--device=test_source',factory.call_args.args[0])
        self.assertEqual(process.terminate.call_count,2)

    def test_stop_while_device_absent(self):
        stop,restart=threading.Event(),threading.Event()
        def factory(*args,**kwargs):
            stop.set()
            raise OSError('absent')
        Audio(stop,restart,lambda:'',Mock(),Mock(),factory,retry_seconds=10).run()

    def test_fragmented_frame(self):
        process=Mock()
        with patch('clap_control.audio.select.select',return_value=([process.stdout],[],[])), \
             patch('clap_control.audio.os.read',side_effect=[bytes(100),bytes(220)]):
            self.assertEqual(read_frame(process,threading.Event(),threading.Event()),bytes(320))

    def test_stall_and_end_of_stream(self):
        with self.assertRaisesRegex(OSError,'stalled'):
            read_frame(Mock(),threading.Event(),threading.Event(),timeout=0)
        process=Mock()
        with patch('clap_control.audio.select.select',return_value=([process.stdout],[],[])), \
             patch('clap_control.audio.os.read',return_value=b''):
            with self.assertRaisesRegex(OSError,'closed'):
                read_frame(process,threading.Event(),threading.Event())
