import { useEffect, useState } from 'react';

export default function useActiveSection(refs){
  const [current,setCurrent] = useState('home');

  useEffect(()=>{
    const io = new IntersectionObserver(entries=>{
      let best=null;
      entries.forEach(e=>{
        if(e.isIntersecting){
          if(!best || e.intersectionRatio>best.r) best={id:e.target.id,r:e.intersectionRatio};
        }
      });
      if(best) setCurrent(best.id)
    },{threshold:[.3,.6,.9]});

    Object.values(refs).forEach(r=>r.current&&io.observe(r.current));
    return ()=>io.disconnect();
  },[]);

  return current;
}
