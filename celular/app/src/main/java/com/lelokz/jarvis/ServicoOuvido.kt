package com.lelokz.jarvis

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

/**
 * "Sempre ouvindo": o "hey Jarvis" com o app fechado ou a tela desligada.
 *
 * O Android só deixa ouvir o microfone em segundo plano com um serviço em
 * primeiro plano, que mostra a notificação fixa "Jarvis está ouvindo" (com o
 * botão Parar). O trabalho de verdade é do `Ouvido`, dentro do `Jarvis` único.
 */
class ServicoOuvido : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val jarvis = (application as App).jarvis
        if (intent?.action == "parar") {
            jarvis.alternarSempreOuvindo(false)
            return START_NOT_STICKY
        }
        val gerente = getSystemService(NotificationManager::class.java)
        gerente.createNotificationChannel(
            NotificationChannel("ouvindo", "NOVA ouvindo", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Aparece enquanto a NOVA espera o \"hey Jarvis\""
                setShowBadge(false)
            })
        val abrir = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE)
        val parar = PendingIntent.getService(this, 1,
            Intent(this, ServicoOuvido::class.java).setAction("parar"), PendingIntent.FLAG_IMMUTABLE)
        val aviso = Notification.Builder(this, "ouvindo")
            .setContentTitle("NOVA está ouvindo")
            .setContentText("Diga \"hey Jarvis\"")
            .setSmallIcon(R.drawable.ic_notificacao)
            .setContentIntent(abrir)
            .setOngoing(true)
            .addAction(Notification.Action.Builder(null, "Parar", parar).build())
            .build()
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(7, aviso, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
            } else {
                startForeground(7, aviso)
            }
        } catch (e: Exception) {
            // Android 14+: reiniciado pelo sistema com o app em segundo plano,
            // ele não deixa abrir o microfone. Desliga quieto; abrir o app religa.
            stopSelf()
            return START_NOT_STICKY
        }
        jarvis.iniciarOuvido()
        return START_STICKY
    }

    override fun onDestroy() {
        (application as App).jarvis.pararOuvido()
        super.onDestroy()
    }
}
