// ScoreGDT-Start.exe - Hilfsprogramm fuer den Hintergrundbetrieb (Zweig "praxis")
//
// medatixx ruft dieses Programm statt scoregdt.exe auf. Es startet in
// Sekundenbruchteilen, meldet sich beim bereits laufenden ScoreGDT dieser
// Windows-Sitzung (Pipe "ScoreGDT-<Sitzungsnummer>") und beendet sich.
// Das laufende ScoreGDT oeffnet dann sofort sein Fenster.
//
// Laeuft kein Hintergrund-ScoreGDT, startet es
//     scoregdt.exe --hintergrund --sofort <Argumente>
// (einmal langsam, danach laeuft der Hintergrundbetrieb).
//
// Wird beim Bau mit dem csc.exe von .NET Framework 4 uebersetzt (C# 5).

using System;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Text;

static class ScoreGdtStart
{
    [DllImport("user32.dll")]
    static extern bool AllowSetForegroundWindow(int dwProcessId);

    const int ASFW_ANY = -1;
    const char TRENNER = '\x1f';

    static int Main(string[] args)
    {
        // Das Fenster von ScoreGDT darf nach vorne kommen (wir wurden von medatixx gestartet)
        AllowSetForegroundWindow(ASFW_ANY);

        int sitzung = Process.GetCurrentProcess().SessionId;
        string pipe = "ScoreGDT-" + sitzung;

        if (PipeVorhanden(pipe) && AnLaufendesSenden(pipe, args))
            return 0;

        // Rueckfall: ScoreGDT selbst starten (Hintergrundbetrieb + sofort ein Fenster)
        string ordner = AppDomain.CurrentDomain.BaseDirectory;
        var psi = new ProcessStartInfo(Path.Combine(ordner, "scoregdt.exe"));
        var sb = new StringBuilder("--hintergrund --sofort");
        foreach (string a in args)
            sb.Append(' ').Append(Zitieren(a));
        psi.Arguments = sb.ToString();
        psi.UseShellExecute = false;
        psi.WorkingDirectory = ordner;
        Process.Start(psi);
        return 0;
    }

    static bool PipeVorhanden(string pipe)
    {
        try
        {
            foreach (string p in Directory.GetFiles(@"\\.\pipe\"))
                if (string.Equals(Path.GetFileName(p), pipe, StringComparison.OrdinalIgnoreCase))
                    return true;
        }
        catch { }
        return false;
    }

    static bool AnLaufendesSenden(string pipe, string[] args)
    {
        try
        {
            using (var c = new NamedPipeClientStream(".", pipe, PipeDirection.InOut))
            {
                c.Connect(1500);
                byte[] nachricht = Encoding.UTF8.GetBytes(string.Join(TRENNER.ToString(), args) + "\n");
                c.Write(nachricht, 0, nachricht.Length);
                c.Flush();
                byte[] antwort = new byte[16];
                IAsyncResult lesen = c.BeginRead(antwort, 0, antwort.Length, null, null);
                if (!lesen.AsyncWaitHandle.WaitOne(3000))
                    return false; // keine Antwort -> Rueckfall
                int n = c.EndRead(lesen);
                return n >= 2 && Encoding.ASCII.GetString(antwort, 0, n).StartsWith("OK");
            }
        }
        catch
        {
            return false;
        }
    }

    static string Zitieren(string a)
    {
        if (a.Length > 0 && a.IndexOfAny(new[] { ' ', '\t', '"' }) < 0)
            return a;
        return "\"" + a.Replace("\"", "\\\"") + "\"";
    }
}
