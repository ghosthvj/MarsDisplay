using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;

namespace UsbScreenProbe
{
    internal static class ProbeTests
    {
        private static int checks;
        private static void Check(bool value, string name)
        {
            checks++;
            if (!value) throw new Exception("FAIL: " + name);
        }

        private sealed class FakeClock : IClock
        {
            public long Milliseconds { get; private set; }
            public void Pause() { Milliseconds += 1000; }
        }

        private sealed class FakePort : IPort
        {
            public string Failure;
            public int Opens, Closes;
            public readonly List<byte[]> Writes = new List<byte[]>();
            public PortSettings Settings;
            public void Open(PortSettings settings)
            {
                Settings = settings;
                Opens++;
                if (Failure == "open") throw new IOException();
                if (Failure == "busy") throw new UnauthorizedAccessException();
            }
            public void Write(byte[] data, int offset, int count)
            {
                if (Failure == "write") throw new IOException();
                Writes.Add(data.Skip(offset).Take(count).ToArray());
            }
            public int Pending { get { if (Failure == "queue") throw new IOException(); return Failure == "drain" ? 1 : 0; } }
            public void Dispose()
            {
                Closes++;
                if (Failure == "close" || Failure == "write") throw new IOException();
            }
        }

        private sealed class FakeChild : IOwnChild
        {
            public bool Finished, Reaped, Killed;
            public int ExitCode { get { return 7; } }
            public bool Wait(int milliseconds) { return Killed ? Reaped : Finished; }
            public void Kill() { Killed = true; }
            public void Dispose() { }
        }

        private static Device Target(string port, string id, int health)
        {
            return new Device(port, id, health);
        }
        private const string Identity = "USB\\VID_1A86&PID_5722\\USB35INCHIPSV2";

        private static int Run(string[] args, string input, Device[] devices, FakePort port,
                               byte[] payload, out string stdout, out string stderr)
        {
            var output = new StringWriter();
            var error = new StringWriter();
            int result = Probe.Run(args, new StringReader(input), output, error,
                delegate { return devices; }, delegate { return port; }, new FakeClock(), payload);
            stdout = output.ToString();
            stderr = error.ToString();
            return result;
        }

        public static int Main(string[] args)
        {
            // These modes exist only in the test executable, never in the shipped program.
            if (args.Length == 1 && args[0] == "--test-hang") { Thread.Sleep(Timeout.Infinite); return 0; }
            if (args.Length == 1 && args[0] == "--test-exit") return 7;
            try
            {
                byte[] payload = Probe.LoadPattern();
                string output, error;
                var valid = new[] { Target("COM5", Identity, 0) };
                var port = new FakePort();
                int code = Run(new[] { "--port", "COM5" }, "SEND COM5\n", valid, port, payload, out output, out error);
                Check(code == 0 && error == "" && output == Probe.Banner + Probe.IdentityLine(valid[0]) +
                    "Type SEND COM5 to send one image: " + Probe.Success + Environment.NewLine, "success output");
                Check(port.Opens == 1 && port.Closes == 1, "one lifecycle");
                Check(port.Settings.Name == "COM5" && port.Settings.Baud == 115200 && port.Settings.DataBits == 8 &&
                    port.Settings.Parity == System.IO.Ports.Parity.None && port.Settings.StopBits == System.IO.Ports.StopBits.One &&
                    port.Settings.Handshake == System.IO.Ports.Handshake.RequestToSend && port.Settings.Dtr &&
                    port.Settings.WriteTimeout == 3000, "serial settings");
                Check(port.Writes.Count == 122 && port.Writes[0].SequenceEqual(new byte[] {0,0,0,0,0,121,100,1,64,1,224,0,0,0,0,0}) &&
                    port.Writes[1].SequenceEqual(new byte[] {0,0,4,253,223,197}), "prefix writes");
                Check(port.Writes.Skip(2).All(x => x.Length == 2560) &&
                    port.Writes.SelectMany(x => x).Count() == 307222 &&
                    port.Writes.Skip(2).SelectMany(x => x).SequenceEqual(payload), "all payload bytes and boundaries");

                foreach (var devices in new[] {
                    new Device[0], new[] { valid[0], valid[0] },
                    new[] { valid[0], Target("COM6", Identity, 0) },
                    new[] { Target("COM5", Identity + "EXTRA", 0) },
                    new[] { Target("COM5", Identity.Replace("5722", "5723"), 0) },
                    new[] { Target("COM5", Identity.Replace("1A86", "1A87"), 0) },
                    new[] { Target("COM5", Identity, 10) },
                    new[] { Target("COM5", null, 0) },
                    new[] { Target("COM6", Identity, 0) } })
                {
                    port = new FakePort();
                    code = Run(new[] { "--port", "COM5" }, "SEND COM5\n", devices, port, payload, out output, out error);
                    Check(code == 4 && output == Probe.Banner && error == Probe.IdentityError + Environment.NewLine &&
                        port.Opens == 0 && port.Writes.Count == 0 && port.Closes == 0, "identity rejected");
                }
                foreach (string input in new[] { "", "cancel\n", "SEND COM6\n" })
                {
                    port = new FakePort();
                    code = Run(new[] { "--port", "COM5" }, input, valid, port, payload, out output, out error);
                    Check(code == 0 && error == "" && output == Probe.Banner + Probe.IdentityLine(valid[0]) +
                        "Type SEND COM5 to send one image: Cancelled; no port opened." + Environment.NewLine && port.Opens == 0, "cancel");
                }
                foreach (string failure in new[] { "open", "busy", "write", "queue", "drain", "close" })
                {
                    port = new FakePort { Failure = failure };
                    code = Run(new[] { "--port", "COM5" }, "SEND COM5\n", valid, port, payload, out output, out error);
                    Check(code == 6 && error == Probe.TransferError + Environment.NewLine &&
                        output == Probe.Banner + Probe.IdentityLine(valid[0]) + "Type SEND COM5 to send one image: " &&
                        port.Opens == 1 && port.Closes == 1, "failure " + failure);
                    Check(port.Writes.Count == (failure == "open" || failure == "busy" || failure == "write" ? 0 : 122), "no retries " + failure);
                }
                foreach (byte[] broken in new[] { new byte[1], new byte[307200] })
                {
                    port = new FakePort();
                    code = Run(new[] { "--port", "COM5" }, "SEND COM5\n", valid, port, broken, out output, out error);
                    Check(code == 5 && output == Probe.Banner && error == Probe.PatternError + Environment.NewLine && port.Opens == 0, "fixture rejection");
                }
                foreach (string[] command in new[] { new[] { "--help" }, new[] { "--list" }, new[] { "--self-test" }, new string[0] })
                {
                    port = new FakePort();
                    code = Run(command, "", valid, port, payload, out output, out error);
                    string expected = command.Length == 0 ? Probe.IdentityLine(valid[0]) +
                        "Choose COMn (Enter cancels): Cancelled; no port opened." + Environment.NewLine :
                        command[0] == "--help" ? Probe.Help : command[0] == "--list" ? Probe.IdentityLine(valid[0]) :
                        Probe.SelfTest + Environment.NewLine;
                    Check(code == 0 && output == Probe.Banner + expected && error == "" && port.Opens == 0 &&
                        port.Writes.Count == 0 && port.Closes == 0, "passive command");
                }
                foreach (string[] command in new[] { new[] { "--unknown" }, new[] { "--port", "COM0" }, new[] { "--port", "COM5 & exit" }, new[] { "--worker", "x" } })
                {
                    port = new FakePort();
                    code = Run(command, "", valid, port, payload, out output, out error);
                    Check(code == 2 && output == "" && error == Probe.ArgumentError + Environment.NewLine + Probe.Help && port.Opens == 0, "invalid CLI");
                }
                port = new FakePort();
                code = Run(new string[0], "COM5\nSEND COM5\n", valid, port, payload, out output, out error);
                Check(code == 0 && error == "" && output == Probe.Banner + Probe.IdentityLine(valid[0]) +
                    "Choose COMn (Enter cancels): " + Probe.IdentityLine(valid[0]) + "Type SEND COM5 to send one image: " +
                    Probe.Success + Environment.NewLine && port.Opens == 1 && port.Writes.Count == 122 && port.Closes == 1,
                    "interactive selection uses same transfer");
                foreach (string choice in new[] { "com5", "COM0", "COM5 & exit" })
                {
                    port = new FakePort();
                    code = Run(new string[0], choice + "\nSEND " + choice + "\n", valid, port, payload, out output, out error);
                    Check(code == 4 && output == Probe.Banner + Probe.IdentityLine(valid[0]) + "Choose COMn (Enter cancels): " &&
                        error == Probe.IdentityError + Environment.NewLine && port.Opens == 0 && port.Writes.Count == 0 && port.Closes == 0,
                        "strict interactive COM name");
                }
                var text = new StringWriter();
                int inventories = 0;
                port = new FakePort();
                code = Probe.Run(new[] { "--port", "COM5" }, new StringReader("SEND COM5\n"), new StringWriter(), text,
                    delegate { inventories++; return inventories == 1 ? valid : new Device[0]; }, delegate { return port; }, new FakeClock(), payload);
                Check(code == 4 && inventories == 2 && port.Opens == 0 && text.ToString() == Probe.IdentityError + Environment.NewLine, "recheck");
                text = new StringWriter();
                code = Probe.Run(new[] { "--list" }, new StringReader(""), new StringWriter(), text,
                    delegate { throw new IOException(); }, delegate { throw new Exception("must not create port"); }, new FakeClock(), payload);
                Check(code == 3 && text.ToString() == Probe.InventoryError + Environment.NewLine, "inventory failure");
                foreach (bool reaped in new[] { false, true })
                {
                    var child = new FakeChild { Reaped = reaped };
                    text = new StringWriter();
                    Check(Supervisor.Wait(child, 1, text) == 8 && child.Killed && text.ToString() ==
                        (reaped ? Supervisor.TimeoutMessage : Supervisor.UncertainMessage) + Environment.NewLine, "owned timeout");
                }
                var finished = new FakeChild { Finished = true };
                Check(Supervisor.Wait(finished, 1, new StringWriter()) == 7 && !finished.Killed, "child exit preserved");
                using (var child = OwnedChild.Start(System.Reflection.Assembly.GetExecutingAssembly().Location, "--test-hang", null))
                    Check(Supervisor.Wait(child, 200, new StringWriter()) == 8 && child.Wait(2000), "real owned hang reaped");
                using (var child = OwnedChild.Start(System.Reflection.Assembly.GetExecutingAssembly().Location, "--test-exit", null))
                    Check(Supervisor.Wait(child, 5000, new StringWriter()) == 7, "real owned exit");
                Console.WriteLine("PASS " + checks + " native checks; no USB opened.");
                return 0;
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); return 1; }
        }
    }
}
