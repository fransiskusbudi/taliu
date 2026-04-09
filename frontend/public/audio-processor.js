/**
 * MicProcessor — AudioWorklet processor for microphone capture.
 *
 * Runs in a separate AudioWorkletGlobalScope thread.
 * Converts Float32 audio from the browser (at the AudioContext sample rate,
 * set to 16000Hz so the browser handles downsampling) to Int16 PCM and
 * posts each buffer to the main thread for forwarding to Deepgram.
 */
class MicProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input || input.length === 0) return true;

    // Boost gain by 2x to improve sensitivity for quieter voices
    const gain = 2.0;

    // Convert Float32 [-1.0, 1.0] → Int16 [-32768, 32767] with gain boost
    const int16 = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const amplified = input[i] * gain;
      int16[i] = Math.max(-32768, Math.min(32767, Math.round(amplified * 32767)));
    }

    // Transfer ownership of the buffer to the main thread (zero-copy)
    this.port.postMessage(int16.buffer, [int16.buffer]);
    return true;
  }
}

registerProcessor("mic-processor", MicProcessor);
