from livekit import rtc
from livekit.rtc import RoomOptions


async def join_livekit_room(url, token):
    room = rtc.Room()
    options = RoomOptions(
        auto_subscribe=True,
        dynacast=True,
    )

    try:
        await room.connect(url, token, options)
        print("成功连接到房间")
    except Exception as e:
        print(f"连接房间失败: {str(e)}")
        raise

    return room
