"""CNN_IMAGE_INSPECTION worker: Kafka -> ONNX MobileNet -> Kafka. RAM-capped; swap in a fine-tuned model for real defects."""
import asyncio, base64, io, json, os, resource
import numpy as np, onnxruntime as ort
from PIL import Image
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

resource.setrlimit(resource.RLIMIT_AS, (int(os.environ.get("MEM_BYTES", 1_800_000_000)),) * 2)
sess = ort.InferenceSession(os.environ.get("MODEL", "/models/mobilenet.onnx"), providers=["CPUExecutionProvider"])
MEAN, STD = np.array([.485, .456, .406], "f"), np.array([.229, .224, .225], "f")

def infer(raw):
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    if im.width * im.height > 25_000_000: raise ValueError("image too large")
    x = ((np.asarray(im.resize((224, 224)), "f") / 255 - MEAN) / STD).transpose(2, 0, 1)[None].astype("f")
    z = sess.run(None, {sess.get_inputs()[0].name: x})[0][0]
    p = np.exp(z - z.max()); p /= p.sum(); i = int(p.argmax())
    return {"class": i, "confidence": round(float(p[i]), 4), "pass": bool(p[i] >= float(os.environ.get("THRESH", .6)))}

async def main():
    kb = os.environ["KAFKA"]
    c = AIOKafkaConsumer("cnn.requests", bootstrap_servers=kb, group_id="cnn", enable_auto_commit=False, max_poll_records=4)  # backpressure
    p = AIOKafkaProducer(bootstrap_servers=kb); await c.start(); await p.start()
    async for m in c:
        j = json.loads(m.value)
        try: out = infer(base64.b64decode(j["image_b64"]))
        except Exception as e: out = {"pass": False, "error": str(e)}
        await p.send_and_wait("cnn.results", json.dumps({"idem": f"{j['workflow_id']}:{j['step_id']}", **out}).encode())
        await c.commit()
asyncio.run(main())
