
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

    def neighbors(self,token,limit=250):
        cur=self.cx.execute("""SELECT address,venue,factory,token0,token1,param FROM pools
                              WHERE token0=? OR token1=? LIMIT ?""",(token.lower(),token.lower(),limit))
        ks=["address","venue","factory","token0","token1","param"]
        return [dict(zip(ks,r)) for r in cur.fetchall()]

    def count_pools(self):
        return self.cx.execute("SELECT COUNT(*) FROM pools").fetchone()[0]

    def get_progress(self,key,default=None):
        r=self.cx.execute("SELECT value FROM progress WHERE key=?",(key,)).fetchone()
        return r[0] if r else default

    def set_progress(self,key,value):
        self.cx.execute("""INSERT INTO progress(key,value,updated_at) VALUES(?,?,?)
                           ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
                        (key,str(value),time.time())); self.cx.commit()
