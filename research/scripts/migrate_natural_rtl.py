"""One-time, reviewable migration from frozen EAE0 to pitch layout 2."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def edit(name,fn):
    p=R/name;p.write_text(fn(p.read_text(encoding='utf8')),encoding='utf8')
def repl(t,a,b):
    assert a in t,a[:100]
    return t.replace(a,b)
for name in ['rtl/playable_synth32.v','rtl/poly_synth32_tm.v','board/pressure_i2s_additive32_core.v']:
    edit(name,lambda t:t.replace('[191:0]','[223:0]').replace('*6 +: 6','*7 +: 7').replace('note_step_table35','note_step_table72'))
edit('rtl/poly_synth32_tm.v',lambda t:t.replace('reg [5:0] pitch_q','reg [6:0] pitch_q'))
edit('rtl/synth_voice.v',lambda t:t.replace('[5:0]         pitch_index','[6:0]         pitch_index'))
def texture(t):
    return t.replace('[5:0] note_index','[6:0] note_index').replace('[0:629]','[0:1295]').replace('630 entries','1296 entries').replace("wire [9:0] address=(timbre ? 10'd315 : 10'd0)+{4'd0,note_index}*10'd9+{7'd0,expression[7:5]};", "wire [10:0] address=(timbre ? 11'd648 : 11'd0)+{4'd0,note_index}*11'd9+{8'd0,expression[7:5]};").replace('note_index<35','note_index<72').replace("address+10'd1","address+11'd1")
edit('rtl/expressive_texture.v',texture)
def allocator(t):
    t=t.replace('[191:0]','[223:0]').replace('[5:0]','[6:0]').replace('6\'d','7\'d').replace('*6 +: 6','*7 +: 7')
    t=repl(t,'    input  wire         banked_enable,','''    input wire [3:0] key,
    input wire guide_override,
    input wire [2:0] guide_pad,
    input wire [6:0] guide_note,
    input wire remote_absolute,
    input wire [6:0] remote_note,
    input  wire         banked_enable,''')
    a=t.index('    wire [6:0] mapped_note =');b=t.index('    function [6:0] note_for_zone;',a)
    t=t[:a]+'''    wire [6:0] natural_note,remote_natural_note;
    wire natural_ok,remote_natural_ok;
    pitch_layout physical_map(.bank(bank),.pad(strike_channel),.key(key),.note_index(natural_note),.valid(natural_ok));
    pitch_layout phone_map(.bank(bank),.pad(remote_strike_channel),.key(key),.note_index(remote_natural_note),.valid(remote_natural_ok));
    wire [6:0] mapped_note=guide_override && strike_channel==guide_pad ? guide_note : natural_note;
    wire banked_strike_ok=natural_ok && mapped_note<72;
    wire [6:0] remote_mapped_note=remote_absolute ? remote_note :
        guide_override && remote_strike_channel==guide_pad ? guide_note : remote_natural_note;
    wire remote_strike_ok=remote_absolute ? remote_note<72 : remote_natural_ok && remote_mapped_note<72;

'''+t[b:]
    for old in [14,12,9,7,4,2,0]:
        t=t.replace(f'note_for_zone = 7\'d{old};',f'note_for_zone = 7\'d{old+24};')
    return t
edit('rtl/strike_voice_allocator32.v',allocator)
def core(t):
    t=t.replace('[5:0] autoplay_note_index','[6:0] autoplay_note_index')
    t=repl(t,'    input wire [2:0] panel_bank,','''    input wire [2:0] panel_bank,
    input wire [3:0] panel_key,
    input wire guide_override,
    input wire [2:0] guide_pad,
    input wire [6:0] guide_note,
    input wire remote_absolute,
    input wire [6:0] remote_note,''')
    t=repl(t,'.remote_strike_valid(remote_strike_valid),','.key(panel_key),.guide_override(guide_override),.guide_pad(guide_pad),.guide_note(guide_note),\n        .remote_absolute(remote_absolute),.remote_note(remote_note),\n        .remote_strike_valid(remote_strike_valid),')
    return t
edit('board/pressure_i2s_additive32_core.v',core)
def player(t):
    t=t.replace('input wire song_select,','input wire song_select,\n    input wire [3:0] key,').replace('[5:0] note_index','[6:0] note_index')
    a=t.index('    assign event_bank =');b=t.index('    // Per-song',a)
    t=t[:a]+'''    wire [6:0] exact_note=7'd24+{4'd0,word_now[5:3]}*7'd7+{4'd0,word_now[2:0]};
    wire [2:0] projected_pad;
    pitch_projection project(.note_index(exact_note),.key(key),.bank(event_bank),.pad(projected_pad),.sharp(),.valid());
    assign event_pad=word_now[2:0]==7 ? 3'd7 : projected_pad;
    assign note_index=exact_note;
'''+t[b:]
    return t
edit('rtl/song_event_player.v',player)
def guide(t):
    t=t.replace('input wire song_select,','input wire song_select,\n    input wire [3:0] key,\n    output wire [6:0] target_note,')
    a=t.index('    assign target_bank =');b=t.index('    assign target_duration_ms',a)
    t=t[:a]+'''    assign target_note=7'd24+{4'd0,target_word[5:3]}*7'd7+{4'd0,target_word[2:0]};
    wire [2:0] projected_bank,projected_pad;
    pitch_projection project(.note_index(target_note),.key(key),.bank(projected_bank),.pad(projected_pad),.sharp(),.valid());
    assign target_bank=completed || song_length==0 ? 3'd0 : projected_bank;
    assign target_pad=completed || song_length==0 || target_word[2:0]==7 || target_word[22] ? 3'd7 : projected_pad;
'''+t[b:]
    return t
edit('rtl/song_guide_long.v',guide)
edit('rtl/front_panel_product.v',lambda t:repl(t,'bank<=0;timbre_select','bank<=2;timbre_select'))
