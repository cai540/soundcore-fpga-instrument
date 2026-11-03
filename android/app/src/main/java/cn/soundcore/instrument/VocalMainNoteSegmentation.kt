package cn.soundcore.instrument

import kotlin.math.*

/** Vocal main-note decoder. No lyrics, song templates, fixed key or file identity.
 * A voiced frame is not an onset: suppress coherent vibrato, bridge pitch-tracker
 * dropouts only over audible sound, then require a sustained note state.
 * This estimates acoustic syllable-like events; it does not recognize words.
 */
internal object VocalMainNoteSegmentation {
    private const val DWELL = 15 // 150 ms main-note plateau; instrument mode is separate.
    private data class Run(val start:Int,val end:Int,val value:Int)
    private fun runs(a:IntArray):List<Run> {
        if(a.isEmpty())return emptyList()
        val out=mutableListOf<Run>();var start=0
        for(i in 1..a.size)if(i==a.size || a[i]!=a[start]) { out+=Run(start,i,a[start]);start=i }
        return out
    }
    private fun median(a:DoubleArray):Double {
        a.sort();return if(a.size%2==1)a[a.size/2] else (a[a.size/2-1]+a[a.size/2])/2
    }
    private fun filtered(a:DoubleArray,radius:Int)=DoubleArray(a.size) { i ->
        median(DoubleArray(radius*2+1){j->a[(i+j-radius).coerceIn(a.indices)]})
    }
    private fun average(a:DoubleArray,start:Int,end:Int):Double {
        var sum=0.0;for(i in start until end)sum+=a[i];return sum/(end-start)
    }

    /** Subtract only a coherent 3..9 Hz oscillation, not an isolated step/ramp.
     * Fit after removing a linear trend over 850 ms; >=65% explained variance
     * is required. Precomputed sin/cos avoids millions of transcendental calls.
     */
    private fun vibratoCenter(p:DoubleArray,cancelled:()->Boolean):DoubleArray {
        val out=p.copyOf()
        val cosine=Array(13){f->DoubleArray(85){k->cos(2*PI*(3+f*.5)*(k-42)*.01)}}
        val sine=Array(13){f->DoubleArray(85){k->sin(2*PI*(3+f*.5)*(k-42)*.01)}}
        for(i in p.indices) {
            if(i%128==0 && cancelled())throw InterruptedException("已取消识别")
            val start=max(0,i-42);val end=min(p.size,i+43);val count=end-start
            if(count<60)continue
            // A periodic sequence of genuine, flat note plateaus also has a
            // sinusoidal component. Require continuous pitch motion first.
            if((start+1 until end).count{abs(p[it]-p[it-1])>.035}<.35*(count-1))continue
            var st=0.0;var stt=0.0;var sy=0.0;var sty=0.0
            for(j in start until end) { val t=(j-i)*.01;st+=t;stt+=t*t;sy+=p[j];sty+=t*p[j] }
            val slope=(sty-st*sy/count)/(stt-st*st/count)
            val intercept=(sy-slope*st)/count
            val residual=DoubleArray(count){j->p[start+j]-intercept-slope*(start+j-i)*.01}
            val variance=residual.sumOf{it*it};if(variance<.04*count)continue
            var best=0.0;var center=0.0
            for(f in cosine.indices) {
                var cc=0.0;var ss=0.0;var cs=0.0;var cy=0.0;var syOsc=0.0
                for(j in residual.indices) {
                    val k=start+j-i+42;val c=cosine[f][k];val s=sine[f][k]
                    cc+=c*c;ss+=s*s;cs+=c*s;cy+=c*residual[j];syOsc+=s*residual[j]
                }
                val determinant=cc*ss-cs*cs;if(determinant<=1e-9)continue
                val a=(cy*ss-syOsc*cs)/determinant;val b=(syOsc*cc-cy*cs)/determinant
                var error=0.0
                for(j in residual.indices) {
                    val k=start+j-i+42;val difference=residual[j]-a*cosine[f][k]-b*sine[f][k]
                    error+=difference*difference
                }
                val explained=1-error/variance
                if(explained>best) { best=explained;center=a }
            }
            if(best>.65)out[i]-=center*min(1.0,(best-.65)/.15)
        }
        return out
    }

    fun segment(track:StablePitchTracker.Track,duration:Int,cancelled:()->Boolean={false},
        onsetEvidence:DoubleArray?=null,minimumDwell:Int=DWELL):MelodyScore = decode(track,duration,cancelled,onsetEvidence,true,minimumDwell)

    fun alternative(track:StablePitchTracker.Track,duration:Int,cancelled:()->Boolean={false},
        onsetEvidence:DoubleArray?=null):MelodyScore = decode(track,duration,cancelled,onsetEvidence,false)

    private fun decode(track:StablePitchTracker.Track,duration:Int,cancelled:()->Boolean,
        onsetEvidence:DoubleArray?,useSlopeWeight:Boolean,dwell:Int=DWELL):MelodyScore {
        require(dwell in 6..15)
        val p=track.pitch.copyOf();val rms=track.rms;val prob=track.probability
        // pYIN's 1% no-trough fallback is not evidence of a musical voice.
        require(prob.count{it>=.1}>=min(6,max(1,p.size/4))) {
            "没有找到稳定人声，请选择清晰的单旋律录音"
        }
        val maximum=rms.maxOrNull()?:0.0;val floor=max(.0025,maximum*.035)
        val energy=filtered(rms,2)
        val active=IntArray(p.size){i->if(p[i].isFinite() && rms[i]>floor)1 else 0}
        for(i in p.indices)if(active[i]==0)p[i]=Double.NaN
        val labels=IntArray(p.size){i->if(active[i]==1)p[i].roundToInt() else -1}
        val smoothed=IntArray(p.size){i->
            val values=IntArray(9){j->labels[(i+j-4).coerceIn(labels.indices)]};values.sort()
            if(active[i]==1)values[4] else -1
        }
        val original=p.copyOf()
        // Repair only short, uncertain octave islands supported on BOTH sides.
        // A sustained/high-confidence real octave remains a real note.
        for(r in runs(smoothed)) {
            if(r.value<0 || r.end-r.start>45 || average(prob,r.start,r.end)>=.45)continue
            val left=original.sliceArray(max(0,r.start-50) until r.start)
                .filter{it.isFinite() && abs(it-r.value)>6}.toDoubleArray()
            val right=original.sliceArray(r.end until min(p.size,r.end+50))
                .filter{it.isFinite() && abs(it-r.value)>6}.toDoubleArray()
            if(left.size<8 || right.size<8)continue
            val a=median(left);val b=median(right)
            for(delta in intArrayOf(-12,12))if(abs(r.value+delta-a)<=3 &&
                abs(r.value+delta-b)<=3 && abs(a-b)<=4) {
                for(i in r.start until r.end)if(p[i].isFinite())p[i]+=delta
                break
            }
        }
        // Interpolate after register repair. Actual silence is never filled.
        for(r in runs(active))if(r.value==0 && r.start>0 && r.end<p.size &&
            r.end-r.start<=16 && active[r.start-1]==1 && active[r.end]==1 &&
            (r.start until r.end).all{rms[it]>floor*1.5}) {
            val a=p[r.start-1];val b=p[r.end];val width=r.end-r.start+1
            for(i in r.start until r.end) { p[i]=a+(b-a)*(i-r.start+1)/width;active[i]=1 }
        }
        val attacks=DoubleArray(p.size);val cuts=mutableListOf<Int>()
        val valleys=mutableListOf<Pair<Int,Int>>()
        for(k in VocalNoteSegmentation.valleys(energy)) {
            val before=(max(0,k-25) until k).maxOf{energy[it]}
            val after=(k+1 until min(p.size,k+26)).maxOf{energy[it]}
            val low=energy[k];val height=min(before,after)
            if(height<floor*3 || height<low*1.75)continue
            val threshold=low+(height-low)*.5;var left=k;var right=k
            while(left>0 && k-left<25 && energy[left-1]<threshold)left--
            while(right+1<p.size && right-k<25 && energy[right+1]<threshold)right++
            val width=right-left+1
            if(width>25 && height<low*3)continue // retain a clear, broad rearticulation
            valleys+=k to width
        }
        for((index,valley) in valleys.withIndex()) {
            val (k,width)=valley
            // A broad consonant can last >90ms. Reject it only if neighbouring
            // valleys show a repeated, fast (>=~3Hz) amplitude oscillation.
            val periodic=(max(0,index-2)..min(index,valleys.size-3)).any { a ->
                val left=valleys[a+1].first-valleys[a].first
                val right=valleys[a+2].first-valleys[a+1].first
                left in 8..35 && right in 8..35 && min(left,right)>=.75*max(left,right)
            }
            if(width>9 && periodic)continue
            if(onsetEvidence!=null) {
                val spectral=onsetEvidence.getOrElse(k){0.0}
                val height=min((max(0,k-25) until k).maxOf{energy[it]},
                    (k+1 until min(p.size,k+26)).maxOf{energy[it]})
                // A clear abrupt rearticulation is valid even for a synthetic
                // steady-spectrum tone. Weak/broad valleys need phonetic change.
                if(spectral<.30 && !(width<=9 && height>=energy[k]*3))continue
            }
            cuts+=k
            for(i in max(0,k-3) until min(p.size,k+13))
                attacks[i]=max(attacks[i],max(0.0,1-abs(i-k)/16.0))
        }
        for(r in runs(active))if(r.value==1) {
            val center=vibratoCenter(filtered(p.sliceArray(r.start until r.end),2),cancelled)
            center.copyInto(p,r.start)
        }
        val observed=p.filter{it.isFinite()}
        require(observed.isNotEmpty()){"没有找到稳定人声，请选择清晰的单旋律录音"}
        val lo=max(24,floor(observed.min()).toInt()-1);val hi=min(108,ceil(observed.max()).toInt()+1)
        val count=hi-lo+1;require(count>=2)
        val histogram=DoubleArray(count)
        for(i in p.indices)if(p[i].isFinite())for(n in 0 until count) {
            val d=(lo+n-p[i])/.3
            histogram[n]+=exp(-.5*d*d)*(.25+.75*min(rms[i]/max(floor,maximum*.3),1.0))
        }
        val peak=histogram.max();val pseudo=max(peak*.02,.01)
        val prior=DoubleArray(count){-.04*ln((histogram[it]+pseudo)/(peak+pseudo))}
        val output=mutableListOf<MelodyNote>();val states=count*dwell
        for(r in runs(active)) {
            if(r.value==0 || r.end-r.start<dwell)continue
            if(r.end-r.start<25 && average(prob,r.start,r.end)<.12 &&
                (r.start until r.end).maxOf{rms[it]}<maximum*.18)continue
            val edge=max(floor,(r.start until r.end).maxOf{energy[it]}*.10)
            val last=(r.start until r.end).lastOrNull{energy[it]>=edge}?:r.end-1
            val end=min(r.end,last+4);val frames=end-r.start
            if(frames<dwell)continue
            val back=ShortArray(frames*states){(-1).toShort()}
            var previous=DoubleArray(states){Double.POSITIVE_INFINITY}
            for(frame in r.start until end) {
                if(frame%128==0 && cancelled())throw InterruptedException("已取消识别")
                val k=frame-r.start
                val delta=abs(p[min(end-1,frame+3)]-p[max(r.start,frame-3)])
                val stable=max(.25,1/(1+(delta/.55).pow(4)))
                val weight=(.6+.4*prob[frame])*(if(useSlopeWeight)stable else 1.0)
                val fit=DoubleArray(count){n->
                    val d=abs(lo+n-p[frame])
                    min(4.0,if(d<=.75)d*d else 1.5*d-.5625)*weight+prior[n]
                }
                if(k==0) { for(n in 0 until count)previous[n*dwell]=fit[n];continue }
                val now=DoubleArray(states){Double.POSITIVE_INFINITY}
                var best=-1;var second=-1
                for(n in 0 until count) {
                    val mature=n*dwell+dwell-1
                    if(best<0 || previous[mature]<previous[best*dwell+dwell-1]) {second=best;best=n}
                    else if(second<0 || previous[mature]<previous[second*dwell+dwell-1])second=n
                    for(age in 1 until dwell) {
                        val target=n*dwell+age
                        now[target]=previous[target-1]+fit[n];back[k*states+target]=(target-1).toShort()
                    }
                    if(previous[mature]<previous[mature-1]) {
                        now[mature]=previous[mature]+fit[n];back[k*states+mature]=mature.toShort()
                    }
                }
                for(n in 0 until count) {
                    val source=(if(n==best)second else best)*dwell+dwell-1
                    val target=n*dwell
                    now[target]=previous[source]+6*(1-.65*attacks[frame])+fit[n]
                    back[k*states+target]=source.toShort()
                }
                previous=now
            }
            var state=(0 until count).minBy{previous[it*dwell+dwell-1]}*dwell+dwell-1
            val decoded=IntArray(frames)
            for(k in frames-1 downTo 0) {
                decoded[k]=lo+state/dwell
                if(k>0)state=back[k*states+state].toInt()
                check(k==0 || state>=0){"人声分段状态不完整"}
            }
            for(note in runs(decoded)) {
                val a=r.start+note.start;val b=r.start+note.end;val boundaries=mutableListOf(a)
                for(cut in cuts)if(cut-a>=20 && b-cut>=20 && cut-boundaries.last()>=20)boundaries+=cut
                boundaries+=b
                for((start,finish) in boundaries.zipWithNext())if(finish-start>=9 && start*10<duration)
                    output+=MelodyNote(start*10,min(finish*10,duration)-start*10,note.value,
                        average(prob,start,finish).toFloat())
            }
        }
        require(output.isNotEmpty()){"没有找到稳定人声，请选择清晰的单旋律录音"}
        return MelodyScore(VocalPlateauGate.apply(output,
            StablePitchTracker.Track(p,prob,rms),cancelled),duration)
    }
}
