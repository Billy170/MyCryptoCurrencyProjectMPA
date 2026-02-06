TARGET_TIME=15
def adjust_vardiff(miner,last_share_time,diff):
    if last_share_time<TARGET_TIME/2: return diff*2
    if last_share_time>TARGET_TIME*2: return max(1,diff//2)
    return diff
