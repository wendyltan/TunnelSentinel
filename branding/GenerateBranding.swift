import AppKit
import Foundation

// Canonical vector geometry for Finder icon and menu-bar template.
enum Brand {
    static func rgb(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> NSColor {
        NSColor(deviceRed:r/255,green:g/255,blue:b/255,alpha:a)
    }
    static func arc(_ c:NSPoint,_ r:CGFloat,from:CGFloat,to:CGFloat,
                    thickness:CGFloat,color:NSColor) {
        let p=NSBezierPath()
        p.appendArc(withCenter:c,radius:r,startAngle:from,endAngle:to)
        p.lineWidth=thickness
        p.lineCapStyle = .round
        color.setStroke()
        p.stroke()
    }
    static func dot(_ c:NSPoint,radius:CGFloat,color:NSColor) {
        let p=NSBezierPath(ovalIn:NSRect(x:c.x-radius,y:c.y-radius,
                                        width:radius*2,height:radius*2))
        color.setFill()
        p.fill()
    }
    static func render(_ pixels:Int,template:Bool) throws -> Data {
        guard let bitmap=NSBitmapImageRep(bitmapDataPlanes:nil,pixelsWide:pixels,pixelsHigh:pixels,
                          bitsPerSample:8,samplesPerPixel:4,hasAlpha:true,isPlanar:false,
                          colorSpaceName:.deviceRGB,bytesPerRow:0,bitsPerPixel:0),
              let graphics=NSGraphicsContext(bitmapImageRep:bitmap) else {
            throw NSError(domain:"Brand",code:1)
        }
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current=graphics
        graphics.imageInterpolation = .high
        graphics.cgContext.scaleBy(x:CGFloat(pixels)/1024,y:CGFloat(pixels)/1024)
        let center=NSPoint(x:512,y:515)
        if !template {
            let background=NSBezierPath(roundedRect:NSRect(x:31,y:31,width:962,height:962),
                                       xRadius:236,yRadius:236)
            background.addClip()
            NSGradient(starting:rgb(10,23,54),ending:rgb(15,104,139))!
                .draw(in:NSRect(x:0,y:0,width:1024,height:1024),angle:45)
            let wash=NSBezierPath(ovalIn:NSRect(x:122,y:210,width:820,height:820))
            NSGradient(starting:rgb(91,244,226,0.20),ending:rgb(28,136,182,0.02))!
                .draw(in:wash,angle:35)
            arc(center,312,from:8,to:174,thickness:20,color:rgb(102,203,238,0.18))
            arc(center,312,from:188,to:338,thickness:20,color:rgb(102,203,238,0.18))
            arc(center,257,from:-53,to:228,thickness:61,color:rgb(11,72,110,0.95))
            arc(center,257,from:-53,to:228,thickness:37,color:rgb(94,225,238))
            arc(center,195,from:-45,to:222,thickness:30,color:rgb(218,252,254,0.97))
            arc(center,195,from:233,to:294,thickness:14,color:rgb(120,238,218,0.44))
            dot(center,radius:93,color:rgb(91,240,223,0.11))
            dot(center,radius:68,color:rgb(193,255,240,0.14))
            dot(center,radius:44,color:rgb(221,255,247))
            dot(center,radius:18,color:rgb(22,124,153))
            dot(NSPoint(x:739,y:741),radius:26,color:rgb(255,213,145))
            dot(NSPoint(x:739,y:741),radius:11,color:rgb(255,248,220))
            arc(center,341,from:115,to:147,thickness:14,color:rgb(164,246,240,0.42))
        } else {
            let ink=NSColor.black
            arc(center,325,from:35,to:145,thickness:91,color:ink)
            arc(center,325,from:160,to:275,thickness:91,color:ink)
            arc(center,205,from:-36,to:217,thickness:95,color:ink)
            dot(center,radius:81,color:ink)
            dot(NSPoint(x:788,y:742),radius:57,color:ink)
        }
        graphics.flushGraphics()
        NSGraphicsContext.restoreGraphicsState()
        guard let png=bitmap.representation(using:.png,properties:[:]) else {
            throw NSError(domain:"Brand",code:2)
        }
        return png
    }
}
@main
struct GenerateBranding {
    static func main() throws {
        guard CommandLine.arguments.count == 2 else {
            throw NSError(domain:"Usage: GenerateBranding <output-dir>",code:3)
        }
        let directory=URL(fileURLWithPath:CommandLine.arguments[1],isDirectory:true)
        try FileManager.default.createDirectory(at:directory,withIntermediateDirectories:true)
        try Brand.render(1024,template:false).write(to:directory.appendingPathComponent("AppIcon-1024.png"))
        try Brand.render(128,template:true).write(to:directory.appendingPathComponent("MenuBarTemplate.png"))
        print("Created",directory.path)
    }
}
