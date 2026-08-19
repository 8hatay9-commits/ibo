import sqlite3, time
from pathlib import Path

SCHEMA="""
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS pools(
 address TEXT PRIMARY KEY,
 venue TEXT NOT NULL,
 factory TEXT NOT NULL,
 token0 TEXT,
 token1 TEXT,
 param INTEGER,
 created_block INTEGER,
 updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS pools_token0 ON pools(token0);
CREATE INDEX IF NOT EXISTS pools_token1 ON pools(token1);
CREATE TABLE IF NOT EXISTS progress(
 key TEXT PRIMARY KEY,
 value TEXT NOT NULL,
 updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS live_stats(
 key TEXT PRIMARY KEY,
 value INTEGER NOT NULL,
 updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS pool_activity(
 address TEXT PRIMARY KEY,
 swap_hits INTEGER NOT NULL DEFAULT 0,
 last_seen REAL NOT NULL DEFAULT 0,
 FOREIGN KEY(address) REFERENCES pools(address)
);
CREATE INDEX IF NOT EXISTS pool_activity_rank ON pool_activity(swap_hits DESC,last_seen DESC);
"""

class DB:
    def __init__(self,path):
        self.path=str(path)
        self.cx=sqlite3.connect(self.path,timeout=30)
        self.cx.executescript(SCHEMA); self.cx.commit()

    def upsert_pool(self,address,venue,factory,token0=None,token1=None,param=None,created_block=None):
        self.cx.execute("""INSERT INTO pools(address,venue,factory,token0,token1,param,created_block,updated_at)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(address) DO UPDATE SET venue=excluded.venue,factory=excluded.factory,
        token0=COALESCE(excluded.token0,pools.token0),token1=COALESCE(excluded.token1,pools.token1),
        param=COALESCE(excluded.param,pools.param),created_block=COALESCE(pools.created_block,excluded.created_block),
        updated_at=excluded.updated_at""",
        (address.lower(),venue,factory.lower(),token0.lower() if token0 else None,token1.lower() if token1 else None,param,created_block,time.time()))
        self.cx.commit()

    def pool(self,address):
        r=self.cx.execute("SELECT address,venue,factory,token0,token1,param,created_block FROM pools WHERE address=?",(address.lower(),)).fetchone()
        if not r:return None
        return dict(zip(["address","venue","factory","token0","token1","param","created_block"],r))

    def touch_pool(self,address,hits=1,seen_at=None):
        seen_at=float(seen_at or time.time())
        self.cx.execute("""INSERT INTO pool_activity(address,swap_hits,last_seen) VALUES(?,?,?)
                           ON CONFLICT(address) DO UPDATE SET
                           swap_hits=pool_activity.swap_hits+excluded.swap_hits,
                           last_seen=MAX(pool_activity.last_seen,excluded.last_seen)""",
                        (address.lower(),int(hits),seen_at))
        self.cx.commit()

    def pool_activity(self,address):
        r=self.cx.execute("SELECT swap_hits,last_seen FROM pool_activity WHERE address=?",(address.lower(),)).fetchone()
        return (int(r[0]),float(r[1])) if r else (0,0.0)

    def neighbors(self,token,limit=250):
        cur=self.cx.execute("""SELECT p.address,p.venue,p.factory,p.token0,p.token1,p.param,
                                     COALESCE(a.swap_hits,0),COALESCE(a.last_seen,0)
                              FROM pools p LEFT JOIN pool_activity a ON a.address=p.address
                              WHERE p.token0=? OR p.token1=?
                              ORDER BY COALESCE(a.swap_hits,0) DESC,COALESCE(a.last_seen,0) DESC,p.updated_at DESC
                              LIMIT ?""",(token.lower(),token.lower(),int(limit)))
        ks=["address","venue","factory","token0","token1","param","swap_hits","last_seen"]
        return [dict(zip(ks,r)) for r in cur.fetchall()]

    def pair_pools(self,token_a,token_b,limit=96):
        a=token_a.lower();b=token_b.lower()
        cur=self.cx.execute("""SELECT p.address,p.venue,p.factory,p.token0,p.token1,p.param,
                                     COALESCE(x.swap_hits,0),COALESCE(x.last_seen,0)
                              FROM pools p LEFT JOIN pool_activity x ON x.address=p.address
                              WHERE (p.token0=? AND p.token1=?) OR (p.token0=? AND p.token1=?)
                              ORDER BY COALESCE(x.swap_hits,0) DESC,COALESCE(x.last_seen,0) DESC,p.updated_at DESC
                              LIMIT ?""",(a,b,b,a,int(limit)))
        ks=["address","venue","factory","token0","token1","param","swap_hits","last_seen"]
        return [dict(zip(ks,r)) for r in cur.fetchall()]

    def active_count(self,window_seconds=3600):
        cutoff=time.time()-float(window_seconds)
        return int(self.cx.execute("SELECT COUNT(*) FROM pool_activity WHERE last_seen>=?",(cutoff,)).fetchone()[0])

    def count_pools(self):
        return self.cx.execute("SELECT COUNT(*) FROM pools").fetchone()[0]

    def get_progress(self,key,default=None):
        r=self.cx.execute("SELECT value FROM progress WHERE key=?",(key,)).fetchone()
        return r[0] if r else default

    def set_progress(self,key,value):
        self.cx.execute("""INSERT INTO progress(key,value,updated_at) VALUES(?,?,?)
                           ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
                        (key,str(value),time.time())); self.cx.commit()
