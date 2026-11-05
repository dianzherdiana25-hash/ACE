// Post-hoc diagnostic only. Do not relabel prespecified hypothesis after viewing OOD.
import {makeBank,sourcePrior,episode,evidencePrediction,label} from './study.mjs';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
const N=24,STEPS=[0,1,2,4,8];
function balanceEpisode(task,arm,seed,weights,prior){
const recorded=episode(task,arm,seed,weights,prior),all={};
for(const k of STEPS){
const seen=new Map(recorded.purchased.slice(0,k).map(x=>[x,label(task,x)]));
const obs=[...seen.entries()],source=arm==="static_transfer"||arm==="static_finetune";
const p0=source?prior:Array(N).fill(.5);
const strength=source?2:.25,nearest=arm==="scratch",evidence=arm==="static_transfer"?[]:obs;
let tp=0,tn=0,pCount=0,nCount=0,brier=0;
const work={predictions:0,pair_ops:0,observations:0};
for(let x=0;x<N;x++){
const y=label(task,x),prob=seen.has(x)?seen.get(x):evidencePrediction(x,evidence,weights,p0[x],strength,work,nearest);
if(y){pCount++;if(prob>=.5)tp++;}
else{nCount++;if(prob<.5)tn++;}
brier+=(prob-y)**2;
}
all[k]={balanced_accuracy:(tp/pCount+tn/nCount)/2,brier_all_domain:brier/N};
}
return all;
}
function balanceStudy(frozen){
const bank=makeBank(frozen.seed),prior=sourcePrior(bank.train),baseW={local:1,parity:0,block:0,global:0,explore:.4},fams=["periodic","double_interval","sparse"];
const arms={};
for(const arm of ["scratch","static_transfer","static_finetune","simple_meta","learned_meta","learned_random"]){
const weights=arm.startsWith("learned")?frozen.fitted.weights:baseW;
const tasks=bank.ood_test,episodes=tasks.map(t=>balanceEpisode(t,arm,frozen.seed,weights,prior));
const familyMap={};
for(const family of fams){const ind=tasks.map((t,i)=>t.family===family?i:null).filter(i=>i!==null);
familyMap[family]={};
for(const k of STEPS)familyMap[family][k]=ind.reduce((acc,i)=>acc+episodes[i][k].balanced_accuracy,0)/ind.length;
}
const by_k={};
for(const k of STEPS)by_k[k]={
balanced_accuracy:episodes.reduce((acc,e)=>acc+e[k].balanced_accuracy,0)/episodes.length,
brier_all_domain:episodes.reduce((acc,e)=>acc+e[k].brier_all_domain,0)/episodes.length
};
const hits=episodes.map(e=>STEPS.find(k=>e[k].balanced_accuracy>=.8)??9);
arms[arm]={by_k,family_balanced_accuracy:familyMap,mean_first_hit_censored_at_9:hits.reduce((a,b)=>a+b,0)/hits.length};
}return {seed:frozen.seed,arms};
}
export {balanceEpisode,balanceStudy};
if(process.argv[1]?.endsWith('posthoc_balanced.mjs')){
 const [input,output]=process.argv.slice(2);
 if(!input||!output)throw Error('usage: node posthoc_balanced.mjs prescore.json diagnostic.json');
 if(existsSync(output))throw Error('refuse overwrite');
 const frozen=JSON.parse(readFileSync(input,'utf8'));
 const per_seed=frozen.map(balanceStudy),aggregate={};
 for(const a of Object.keys(per_seed[0].arms)){aggregate[a]={};for(const k of STEPS)
 aggregate[a][k]={balanced_accuracy:per_seed.reduce((v,o)=>v+o.arms[a].by_k[k].balanced_accuracy,0)/per_seed.length,
 brier_all_domain:per_seed.reduce((v,o)=>v+o.arms[a].by_k[k].brier_all_domain,0)/per_seed.length};}
 writeFileSync(output,JSON.stringify({status:'POSTHOC_DIAGNOSTIC_NOT_PRESPECIFIED',seeds:[0,1,2,3],no_change_to_original_H1:true,full_domain_includes_purchased_points:true,per_seed,aggregate},null,2)+'\n');
}
