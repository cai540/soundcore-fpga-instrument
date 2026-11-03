from package_handpan_trial_20261102 import ReleaseConfig,main

if __name__=='__main__':
 main(ReleaseConfig(slug='handpan_rock_20261102',version_code=21,version_name='0.21-handpan-rock-offline',user_code=0x4852,
  apk_name='声芯乐动_0.21_空灵与金属.apk',firmware_name='声芯乐动_空灵与金属_完整音响版_4852.fs',label='空灵与金属',
  tone_names=('二胡','口琴','空灵手碟','金属电音'),minimum_tests=299,
  extra_hdl=('rtl/rock_voice_fx.v',),extra_tests=('fx','oled'),extra_snapshots=(('metal','金属演奏页面.png'),),
  extra_sources=('rtl/rock_voice_fx.v','rtl/rock_softclip.mem','tb/tb_rock_voice_fx.v','tb/tb_rock_oled.v','tb/tb_airy_metal_render.v',
   'scripts/build_handpan_rock_20261102.py','scripts/check_handpan_rock_20261102.py','scripts/render_handpan_rock_20261102.py',
   'scripts/package_handpan_rock_20261102.py','docs/plans/2026-11-02-handpan-rock.md')))
