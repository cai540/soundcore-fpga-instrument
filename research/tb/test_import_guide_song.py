import csv
import tempfile
import unittest
from pathlib import Path

from import_guide_song import import_song


class SongImportTest(unittest.TestCase):
    def test_continuation_flag_does_not_overflow_playback_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'melisma.csv'
            source.write_text('step,midi,duration_ms,guide_continuation\n0,72,700,0\n1,74,350,1\n2,rest,250,0\n3,76,800,0\n',encoding='utf-8')
            result=import_song(source,root/'out',1,'test')
            words=[int(line,16) for line in (root/'out/song_1.mem').read_text().split()]
            self.assertEqual(result['guide_continuation_count'],1)
            self.assertEqual([bool(x&(1<<22)) for x in words],[False,True,False,False])
            self.assertEqual([(x>>6)&65535 for x in words],[700,350,250,800])
            source.write_text('step,midi,duration_ms,guide_continuation\n0,72,700,1\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'first pitched event'):import_song(source,root/'out',1,'test')
            source.write_text('step,midi,duration_ms,guide_continuation\n0,72,700,0\n1,rest,300,1\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'rest cannot'):import_song(source,root/'out',1,'test')

    def test_rest_is_silent_event_not_a_playable_key(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "with_rest.csv"
            source.write_text("step,midi,duration_ms\n0,rest,300\n1,62,450\n",
                              encoding="utf-8")
            result = import_song(source, root / "out", 0, "test")
            self.assertEqual(1, result["rest_count"])
            words = [int(line, 16) for line in (root / "out/song_0.mem")
                     .read_text(encoding="ascii").splitlines()]
            self.assertEqual((300 << 6) | 7, words[0])
            self.assertEqual((450 << 6) | 2, words[1])

    def test_packs_35_note_mapping_and_rejects_unplayable_note(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "confirmed.csv"
            with source.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(("step", "midi", "duration_ms"))
                writer.writerow((0, 60, 400))
                writer.writerow((1, 67, 500))
                writer.writerow((2, 94, 600))
            result = import_song(source, root / "out", 0, "test")
            self.assertEqual(3, result["note_count"])
            words = [int(line, 16) for line in (root / "out/song_0.mem")
                     .read_text(encoding="ascii").splitlines()]
            self.assertEqual([(400 << 6), (500 << 6) | (1 << 3),
                              (600 << 6) | (4 << 3) | 6], words)
            with source.open("a", encoding="utf-8", newline="") as stream:
                csv.writer(stream).writerow((3, 95, 100))
            with self.assertRaisesRegex(ValueError, "outside 60..94"):
                import_song(source, root / "out", 0, "test")


if __name__ == "__main__":
    unittest.main()
