module product_tools_subsystem(
 input wire clk,rst_n,link_active,interrupt,
 input wire request_valid,input wire[7:0] request_type,request_length,input wire[111:0] request_payload,
 output wire response_valid,output wire[111:0] response_payload,
 input wire[6:0] bulk_index,output wire[7:0] bulk_byte,output wire response_bulk,
 input wire sample_tick,input wire signed[15:0] sample_in,
 input wire[5:0] active_voices,input wire deadline_fault,
 output wire diag_enabled,output wire[31:0] diag_gate,output wire[223:0] diag_notes,
 output wire[1:0] view_mode,output wire map_enabled,output wire[48:0] pad_map,output wire clear_voices,
 input wire oled_frame_latch,oled_ready,input wire display_phase_bank,input wire[9:0] phase_address,
 output wire phase_bank,output wire[7:0] phase_pixels,
 output wire[511:0] wave_data,output wire[255:0] spectrum_data,output wire frame_pending);
 wire[511:0] phase_data;wire pending_frame;wire[15:0] frame_id;
 assign frame_pending=pending_frame;
 reg[21:0] fallback_count;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)fallback_count<=0;
  else if(oled_ready || fallback_count==2457599)fallback_count<=0;
  else fallback_count<=fallback_count+1'b1;
 end
 product_audio_analyzer analyzer(.clk(clk),.rst_n(rst_n),.sample_tick(sample_tick),.sample_in(sample_in),
  .frame_latch(oled_frame_latch || (!oled_ready && fallback_count==2457599)),.pending_frame(pending_frame),.frame_id(frame_id),
  .wave_data(wave_data),.spectrum_data(spectrum_data),.phase_data(phase_data),.phase_bank(phase_bank),
  .display_phase_bank(display_phase_bank),.phase_address(phase_address),.phase_pixels(phase_pixels));
 wire record_start,record_stop,recording,record_ready;wire[15:0] record_token,stored_token,record_crc;
 wire[16:0] record_samples;wire[14:0] record_address;wire[7:0] record_byte;
 audio_record_adpcm recorder(.clk(clk),.rst_n(rst_n),.sample_tick(sample_tick),.sample_in(sample_in),
  .start(record_start),.stop(record_stop),.start_token(record_token),.recording(recording),.ready(record_ready),
  .sample_count(record_samples),.token(stored_token),.crc16(record_crc),.read_address(record_address),.read_data(record_byte));
 product_tools_engine tools(.clk(clk),.rst_n(rst_n),.link_active(link_active),.interrupt(interrupt),
  .request_valid(request_valid),.request_type(request_type),.request_length(request_length),.request_payload(request_payload),
  .response_valid(response_valid),.response_payload(response_payload),.bulk_index(bulk_index),.bulk_byte(bulk_byte),.response_bulk(response_bulk),.active_voices(active_voices),.deadline_fault(deadline_fault),
  .analysis_frame(frame_id+1'b1),.analysis_ready(pending_frame),.wave_data(wave_data),.spectrum_data(spectrum_data),.phase_data(phase_data),
  .diag_enabled(diag_enabled),.diag_gate(diag_gate),.diag_notes(diag_notes),.view_mode(view_mode),
  .map_enabled(map_enabled),.pad_map(pad_map),.clear_voices(clear_voices),
  .record_start(record_start),.record_stop(record_stop),.record_token(record_token),.recording(recording),.record_ready(record_ready),
  .record_samples(record_samples),.stored_token(stored_token),.record_crc(record_crc),.record_address(record_address),.record_byte(record_byte));
endmodule
