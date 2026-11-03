"""Same inference policy for any recording; all arguments are acoustic outputs.

The first input is the frozen generic v6 syllable schedule. No identity,
reference score, transcript, known key, bookmark or expected note count enters.
"""
from context_pitch_consensus import refine_context
from recording_tonality import infer_collection
from recording_motif_consensus import refine_repeats
from context_register_decoder import refine_context_register
from sustained_note_components import recover_components
from unsupported_note_events import cleanup

VERSION='register-components-research-v7'


def decode(notes,views,evidence,pesto,crepe,basic,acoustic=None):
    tonal=infer_collection(notes)
    contextual,context_audit=refine_context(notes,views,evidence,pesto,tonal)
    # Repeats are evidence only. Their proposed replacements are not adopted
    # wholesale because intended octave variations can occur between repeats.
    _,motif_audit=refine_repeats(contextual,basic,crepe)
    registered,register_audit=refine_context_register(contextual,views,evidence,pesto,crepe,basic,
                                                   infer_collection(contextual),motif_audit)
    output,component_audit=recover_components(registered,views,evidence,pesto,basic,infer_collection(registered))
    cleanup_audit={'skipped_no_acoustic_features':True}
    if acoustic is not None:output,cleanup_audit=cleanup(output,evidence,pesto,basic,acoustic)
    return output,{'version':VERSION,'reference_lyrics_or_identity_used':False,'context':context_audit,
                    'motif':motif_audit,'register':register_audit,'components':component_audit,
                    'cleanup':cleanup_audit,'old_notes':len(notes),'new_notes':len(output),'real_world_90_percent_verified':False}
