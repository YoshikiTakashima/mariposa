import sqlite3
from db_utils import *
import scipy.stats as stats
import numpy as np
import math
from tqdm import tqdm

def as_seconds(milliseconds):
    return round(milliseconds / 1000, 2)

def as_percentage(p):
    return round(p * 100, 2)

CUR_SOLVERS = ["cvc5-1.0.3", "z3-4.4.2", "z3-4.11.2"]

cfg = ExpConfig("test2", CUR_SOLVERS, [])

con = sqlite3.connect(DB_PATH)
cur = con.cursor()
unstable_table_name = "unstable_" + cfg.table_name

def build_unstable_table():
    cur.execute(f"""DROP TABLE IF EXISTS {unstable_table_name}""")

    cur.execute(f"""CREATE TABLE {unstable_table_name} (
        solver varchar(10),
        vanilla_path varchar(255),
        v_result_code varchar(10),
        v_elapsed_milli INTEGER,
        shuffle_summary varchar(100),
        rename_summary varchar(100),
        sseed_summary varchar(100)
        )""")

    for solver in CUR_SOLVERS:
        res = cur.execute(f"""
            SELECT query_path, result_code, elapsed_milli
            FROM {cfg.table_name}
            WHERE query_path = vanilla_path
            AND command LIKE ?
            """, (f"%{solver}%", ))

        vanilla_rows = res.fetchall()
        for (vanilla_path, v_rcode, v_time) in tqdm(vanilla_rows):
            # if v_rcode != 'unsat':
            #     print("???")
            #     print(vanilla_path)
            #     print(vanilla_path, v_rcode, v_time)
            
            res = cur.execute("DROP VIEW IF EXISTS query_view");
            res = cur.execute(f"""
                CREATE VIEW query_view AS
                SELECT result_code, elapsed_milli, perturbation FROM {cfg.table_name}
                WHERE query_path != vanilla_path
                AND command LIKE "%{solver}%" 
                AND vanilla_path = "{vanilla_path}" """)

            results = dict()

            for perturb in ALL_MUTS:
                res = cur.execute(f"""
                    SELECT * FROM query_view
                    WHERE perturbation = ?
                    """, (perturb,))
                rows = res.fetchall()
                sample_size = len(rows)
                veri_times = [r[1] for r in rows]
                veri_res = [1 if r[0] == 'unsat' else 0 for r in rows]
                p = sum(veri_res) / sample_size

                t_critical = stats.t.ppf(q=cfg.confidence_level, df=sample_size-1)  
                # get the sample standard deviation
                time_stdev = np.std(veri_times, ddof=1)
                results[perturb] = (as_percentage(p), as_seconds(time_stdev), sample_size)

            maybe = False
            for perturb, (p, _, _) in results.items():
                if p <= 0.9:
                    maybe = True
            if maybe:
                summaries = []
                for perturb, (p, std, sz) in results.items():
                    summary = [perturb, p, std, sz]
                    summaries.append(str(summary))

                cur.execute(f"""INSERT INTO {unstable_table_name}
                    VALUES(?, ?, ?, ?, ?, ?, ?);""", (solver, vanilla_path, v_rcode, v_time, summaries[0], summaries[1], summaries[2]))
    con.commit()


for solver in CUR_SOLVERS:
    res = cur.execute(f"""SELECT COUNT(*) FROM {cfg.table_name}
            WHERE query_path == vanilla_path
            AND command LIKE "%{solver}%" """)
    v_count = res.fetchall()[0][0]

    res = cur.execute(f"""SELECT * FROM {unstable_table_name}
        WHERE solver = ?""", (solver, ))
    rows = res.fetchall()
    print("solver " + solver)
    maybe = 0
    for row in rows:
        shuffle_summary = eval(row[4])
        rename_summary = eval(row[5])
        sseed_summary = eval(row[6])
        if shuffle_summary[1] != 0 or rename_summary[1] != 0 or sseed_summary[1] != 0:
            maybe += 1

    print(f"# vanilla queries: {v_count}")
    print(f"# vanilla queries with <= 90% success rate in any mut group: {len(rows)}")
    print(f"# vanilla queries with > 0% success rate in any mut group: {maybe}")
    print("")

# for (vanilla_path, v_rcode, v_time) in vanilla_rows:

#         for perturb in ALL_MUTS:
#             res = cur.execute(f"""
#                 SELECT * FROM query_view
#                 WHERE perturbation = ?
#                 AND command LIKE ?
#                 """, (perturb, f"%{solver}%"))


#             veri_times = [r[7] for r in rows]
#             veri_res = [1 if r[6] == 'unsat' else 0 for r in rows]

#             # if p <= 0.9:
#             # print(vanilla_path, perturb)
#                 # print([r[6] for r in rows])
#                 # print(len(rows))


# con.close()

