import { useEffect, useState } from 'react';
import ContestantCard from './ContestantCard';
import styles from './Contestants.module.css';

/*  В mock.json положен демо-список.
    Для реального API замените fetch ниже.  */
export default function ContestantGrid({openVote}){
  const [list,setList] = useState([]);

  useEffect(()=>{
    (async ()=>{
      try{
        const mock = await import('./mock.json');
        setList(mock.default);
        // --- живой бекенд ---
        // const res = await fetch(import.meta.env.VITE_API_URL+'/results');
        // const {results}=await res.json(); setList(results);
      }catch(e){console.error(e);}
    })();
  },[]);

  return(
    <section className={styles.section}>
      <div className="container">
        <h2>Участницы конкурса</h2>
        <div className={styles.grid}>
          {list.map((c,i)=>(
            <ContestantCard key={c.candidate_id} data={c} number={i+1} onVote={openVote}/>
          ))}
        </div>
      </div>
    </section>
  );
}
