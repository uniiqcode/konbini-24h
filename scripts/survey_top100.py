"""再生数の多いショートを足して、上位100本を言語別に分ける。

先に survey_language.py を実行して data/survey/videos.json を作っておく。
検索語ごとに「再生数の多い順」を1ページずつ取る（約1,800ユニット）。
対象: 60秒以下、タイトルに「日本」と「コンビニ（店名を含む）」の両方が入るもの。
言語: タイトルの文字（かな・ハングル・タイ文字・ベトナム語の記号など）で判定し、
ラテン文字だけなら動画の音声言語の設定、それもなければ英語とする。
"""
import json,os,re,sys
from collections import Counter
sys.path.insert(0,os.path.dirname(__file__))
import survey_language as k
D=os.path.join(os.path.dirname(__file__),"..","data","survey")
VIDEOS=os.path.join(D,"videos.json"); TOP=os.path.join(D,"top100.json")
data=json.load(open(VIDEOS));vids=data["videos"]
new=[]
for lang,qs in k.QUERIES.items():
    for q in qs:
        r=k.get("search",part="id",type="video",q=q,videoDuration="short",relevanceLanguage=lang,maxResults=50,order="viewCount")
        new+=[i["id"]["videoId"] for i in r["items"] if i["id"]["videoId"] not in vids]
new=list(set(new))
for i in range(0,len(new),50):
    r=k.get("videos",part="snippet,contentDetails,statistics",id=",".join(new[i:i+50]))
    for v in r["items"]:
        vids[v["id"]]=dict(sec=k.seconds(v["contentDetails"].get("duration")),audio=(v["snippet"].get("defaultAudioLanguage") or "unknown").split("-")[0],
            views=int(v.get("statistics",{}).get("viewCount",0)),title=v["snippet"]["title"],channel=v["snippet"]["channelTitle"])
data["videos"]=vids;json.dump(data,open(VIDEOS,"w"),ensure_ascii=False,indent=1)
kw=re.compile(r"konbini|conbini|combini|コンビニ|convenience|便利店|便利商店|편의점|セブン|7-?eleven|7-?11|seven|ファミマ|familymart|family mart|ローソン|lawson|ร้านสะดวกซื้อ|tiện lợi|minimarket|supérette|conveniencia|conveniência|세븐|패밀리마트|로손|全家|罗森|羅森|lawson",re.I)
japan=re.compile(r"japan|japon|japão|jepang|nhật|日本|일본|ญี่ปุ่น|コンビニ|セブン|ファミマ|ローソン|konbini|conbini|combini|tokyo|osaka|東京|大阪",re.I)
def script(t):
    if re.search(r"[぀-ヿ]",t): return "ja"
    if re.search(r"[가-힯]",t): return "ko"
    if re.search(r"[฀-๿]",t): return "th"
    if re.search(r"[一-鿿]",t): return "zh"
    if re.search(r"[ăđơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]",t,re.I): return "vi"
    return "latin"
pool=[dict(id=i,**v) for i,v in vids.items() if v["sec"] and v["sec"]<=60 and kw.search(v["title"]) and japan.search(v["title"])]
pool.sort(key=lambda v:-v["views"]);top=pool[:100]
for v in top: v["lang"]=script(v["title"].split("#")[0]) or script(v["title"]) or (v["audio"] if v["audio"] not in("unknown","zxx") else "en")
print("pool",len(pool),"added",len(new))
print(Counter(v["lang"] for v in top).most_common())
vs=Counter()
for v in top: vs[v["lang"]]+=v["views"]
print({a:round(b/1e6,1) for a,b in vs.most_common()})
print("100th views",top[-1]["views"],"1st",top[0]["views"])
for n,v in enumerate(top[:100],1): print(n,v["lang"],v["views"],v["sec"],v["channel"][:20],"|",v["title"][:70])
json.dump(top,open(TOP,"w"),ensure_ascii=False,indent=1)
