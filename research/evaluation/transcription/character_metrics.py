"""Exact register/pitch evaluation of a requested reduced character melody.

Only ordered score-supported single or two-tone realizations are valid.
This does not score rhythm or turn a snippet into a whole-song result.
"""
def compare(units,observed):
    cells={(0,0):(0,())}
    for i in range(len(units)+1):
        for j in range(len(observed)+1):
            if i==j==0:continue
            options=[]
            if i:
                cost,path=cells[i-1,j]
                options.append((cost+1,path+({'kind':'missing','character_index':i-1},)))
            if j:
                cost,path=cells[i,j-1]
                options.append((cost+1,path+({'kind':'extra','observed_index':j-1,'midi':observed[j-1]},)))
            if i:
                choices=units[i-1]['allowed_sequences']
                for length in (1,2):
                    if length>j or not any(len(s)==length for s in choices):continue
                    pitches=observed[j-length:j]
                    correct=pitches in choices
                    cost,path=cells[i-1,j-length]
                    options.append((cost+(not correct),path+({'kind':'correct' if correct else 'wrong_pitch',
                        'character_index':i-1,'character':units[i-1]['character'],
                        'observed_indices':list(range(j-length,j)),'observed':pitches,'allowed':choices},)))
            cells[i,j]=min(options,key=lambda v:(v[0],sum(p['kind'] in ('extra','missing') for p in v[1])))
    errors,path=cells[len(units),len(observed)]
    counts={k:sum(p['kind']==k for p in path) for k in ['correct','wrong_pitch','missing','extra']}
    return {**counts,'reference_characters':len(units),'predicted_notes':len(observed),
        'strict_character_melody_consistency':max(0.,1-errors/max(len(units),1)),
        'rhythm_accuracy_measured':False,'path':list(path)}

def gate(rows):
    scores=sorted([r['strict_character_melody_consistency'] for r in rows],reverse=True)
    identifiers=[r.get('id') for r in rows]
    distinct=len(rows)>=3 and all(identifiers) and len(set(identifiers))==len(rows)
    return {'target':'fixed-40s-character-reduction-only','thresholds':[.99,.95,.95],
        'passed':distinct and scores[0]>=.99 and scores[1]>=.95 and scores[2]>=.95,
        'whole_song_accuracy_claimed':False,'human_listening_passed':False}


def compare_groups(units, observed_groups):
    """Check ownership too: a neighbor's right pitch cannot rescue a word.

    This positional test is valid only when the automatic and reference
    proposal counts agree. Text recognition itself is not being scored.
    Keep the older edit-sequence metric separately for historical comparison.
    """
    if len(units) != len(observed_groups):
        return {'scorable':False,'reason':'automatic and reference unit counts differ',
                'reference_characters':len(units),'predicted_groups':len(observed_groups),
                'strict_character_melody_consistency':0.,'rhythm_accuracy_measured':False}
    rows=[]
    for i,(unit,notes) in enumerate(zip(units,observed_groups)):
        values=[int(v) for v in notes]
        correct=1<=len(values)<=2 and values in unit['allowed_sequences']
        rows.append({'character_index':i,'character':unit['character'],
                     'observed':values,'allowed':unit['allowed_sequences'],'correct':correct})
    count=sum(r['correct'] for r in rows)
    return {'scorable':True,'metric':'exact-carrier-and-unit-ownership',
            'correct':count,'wrong_groups':len(rows)-count,
            'reference_characters':len(units),'predicted_groups':len(observed_groups),
            'predicted_notes':sum(map(len,observed_groups)),
            'strict_character_melody_consistency':count/max(1,len(rows)),
            'rhythm_accuracy_measured':False,'recognized_lyrics_accuracy_measured':False,
            'path':rows}
